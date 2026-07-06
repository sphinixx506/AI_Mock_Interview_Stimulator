import streamlit as st
import uuid
import requests

BACKEND_URL = "http://localhost:8000"

st.set_page_config(page_title="AI Mock Interview - Velira", page_icon="🎤")

st.title("🎤 AI Mock Interview Simulator")
st.caption("Step 4: Full interview loop + /end-interview feedback report.")

# Keep a stable session_id for this browser session
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# Tracks whether the interview has been started against the backend
if "interview_started" not in st.session_state:
    st.session_state.interview_started = False

st.write(f"**Session ID:** `{st.session_state.session_id}`")

with st.form("profile_form"):
    st.subheader("Candidate Profile")

    candidate_name = st.text_input("Full Name", placeholder="e.g. Shristi Sharma")

    domain = st.text_input("Domain / Target Role", placeholder="e.g. Data Science, Backend Development")

    skills_raw = st.text_input(
        "Key Skills (comma-separated)",
        placeholder="e.g. Python, FastAPI, SQL, Machine Learning"
    )

    col1, col2 = st.columns(2)
    with col1:
        experience_level = st.selectbox(
            "Experience Level",
            ["Intern", "Fresher", "Junior", "Mid-level", "Senior"]
        )
    with col2:
        years_of_experience = st.number_input(
            "Years of Experience", min_value=0, max_value=40, value=0, step=1
        )

    education = st.text_input("Education", placeholder="e.g. B.Tech in Computer Science")

    key_projects_raw = st.text_area(
        "Key Projects (one per line, leave blank if none)",
        placeholder="e.g. Built a resume parser using pypdf and Gemini\nBuilt a state-machine driven interview backend"
    )

    certifications_raw = st.text_input(
        "Certifications (comma-separated, optional)",
        placeholder="e.g. AWS Certified Developer"
    )

    col3, col4 = st.columns(2)
    with col3:
        company_type = st.selectbox("Company Style", ["General", "Startup", "FAANG"])
    with col4:
        interview_tone = st.selectbox("Interview Tone", ["Friendly", "Direct", "Stressful"])

    submitted = st.form_submit_button("Save Profile")

if submitted:
    # Parse comma / newline separated fields into clean lists
    skills = [s.strip() for s in skills_raw.split(",") if s.strip()]
    key_projects = [p.strip() for p in key_projects_raw.split("\n") if p.strip()]
    certifications = [c.strip() for c in certifications_raw.split(",") if c.strip()]

    profile = {
        "session_id": st.session_state.session_id,
        "candidate_name": candidate_name,
        "domain": domain,
        "skills": skills,
        "experience_level": experience_level,
        "years_of_experience": int(years_of_experience),
        "education": education,
        "key_projects": key_projects,
        "certifications": certifications,
        "company_type": company_type,
        "interview_tone": interview_tone,
    }

    st.session_state.profile = profile

    # Basic validation before calling the backend
    if not candidate_name.strip() or not domain.strip():
        st.error("Please fill in at least your name and domain before starting.")
    else:
        with st.spinner("Connecting to Velira..."):
            try:
                response = requests.post(
                    f"{BACKEND_URL}/start-interview",
                    json=profile,
                    timeout=60,
                )
            except requests.exceptions.ConnectionError:
                st.error(
                    "Could not reach the backend at "
                    f"{BACKEND_URL}. Make sure `uvicorn main:app --reload` "
                    "is running in a separate terminal."
                )
                response = None

        if response is not None:
            if response.status_code == 200:
                data = response.json()
                st.session_state.interview_started = True
                st.session_state.current_state = "warmup"
                st.session_state.interview_complete = False
                # transcript holds the full back-and-forth for display
                st.session_state.transcript = [
                    {
                        "role": "velira",
                        "text": data["message"],
                        "audio": data.get("audio_file"),
                        "flagged": False,
                    }
                ]
                st.rerun()
            else:
                st.error(f"Backend error ({response.status_code}): {response.text}")

# ============================================================
# INTERVIEW LOOP — shows transcript so far + lets candidate reply
# ============================================================
if st.session_state.interview_started:
    st.divider()
    stage_label = "completed" if st.session_state.get("interview_complete") else st.session_state.get("current_state", "warmup")
    st.subheader(f"Stage: {stage_label}")

    transcript = st.session_state.get("transcript", [])

    # Render the full conversation so far
    for i, turn in enumerate(transcript):
        is_last = (i == len(transcript) - 1)
        if turn["role"] == "velira":
            label = "**Velira:**" if not turn.get("flagged") else "**Velira (guardrail):**"
            st.write(label)
            st.write(turn["text"])
            # Only fetch/play audio for the most recent Velira message,
            # to avoid re-downloading every clip on every rerun
            if is_last and turn.get("audio"):
                audio_response = requests.get(f"{BACKEND_URL}/audio/{turn['audio']}")
                if audio_response.status_code == 200:
                    st.audio(audio_response.content, format="audio/mp3")
                else:
                    st.warning("Could not load audio for this message.")
        else:
            st.write("**You:**")
            st.write(turn["text"])
        st.write("")

    # ── Candidate reply form (only while interview is still running) ──────
    if not st.session_state.get("interview_complete"):
        with st.form("reply_form", clear_on_submit=True):
            candidate_answer = st.text_area("Your answer", key="candidate_answer_input")
            send = st.form_submit_button("Send Answer")

        if send:
            if not candidate_answer.strip():
                st.warning("Please type an answer before sending.")
            else:
                # Show the candidate's answer immediately in the transcript
                st.session_state.transcript.append({
                    "role": "candidate",
                    "text": candidate_answer,
                })

                with st.spinner("Velira is thinking..."):
                    try:
                        reply_response = requests.post(
                            f"{BACKEND_URL}/reply",
                            json={
                                "session_id": st.session_state.session_id,
                                "candidate_answer": candidate_answer,
                            },
                            timeout=60,
                        )
                    except requests.exceptions.ConnectionError:
                        st.error(
                            "Could not reach the backend at "
                            f"{BACKEND_URL}. Make sure the backend is still running."
                        )
                        reply_response = None

                if reply_response is not None:
                    if reply_response.status_code == 200:
                        reply_data = reply_response.json()

                        st.session_state.transcript.append({
                            "role": "velira",
                            "text": reply_data["message"],
                            "audio": reply_data.get("audio_file"),
                            "flagged": reply_data.get("flagged", False),
                        })

                        st.session_state.current_state = reply_data.get("current_state", st.session_state.current_state)

                        if reply_data.get("flagged"):
                            st.session_state.pop("_last_flag_reason", None)
                            st.session_state["_last_flag_reason"] = reply_data.get("flag_reason")

                        if st.session_state.current_state == "completed":
                            st.session_state.interview_complete = True

                        st.rerun()
                    else:
                        st.error(f"Backend error ({reply_response.status_code}): {reply_response.text}")
    else:
        st.success("Interview complete!")

        if "feedback_report" not in st.session_state:
            if st.button("Get Feedback Report"):
                candidate_name = st.session_state.profile.get("candidate_name", "Candidate")

                with st.spinner("Velira is preparing your feedback report..."):
                    try:
                        end_response = requests.post(
                            f"{BACKEND_URL}/end-interview",
                            json={
                                "session_id": st.session_state.session_id,
                                "candidate_name": candidate_name,
                            },
                            timeout=90,
                        )
                    except requests.exceptions.ConnectionError:
                        st.error(
                            "Could not reach the backend at "
                            f"{BACKEND_URL}. Make sure the backend is still running."
                        )
                        end_response = None

                if end_response is not None:
                    if end_response.status_code == 200:
                        end_data = end_response.json()
                        st.session_state.feedback_report = end_data["feedback_report"]
                        st.session_state.feedback_audio = end_data.get("audio_file")
                        st.session_state.db_payload = end_data.get("db_payload")
                        st.rerun()
                    else:
                        st.error(f"Backend error ({end_response.status_code}): {end_response.text}")
        else:
            # ── Display the feedback report ────────────────────────────────
            st.divider()
            st.subheader("📋 Feedback Report")
            st.markdown(st.session_state.feedback_report)

            feedback_audio = st.session_state.get("feedback_audio")
            if feedback_audio:
                audio_response = requests.get(f"{BACKEND_URL}/audio/{feedback_audio}")
                if audio_response.status_code == 200:
                    st.audio(audio_response.content, format="audio/mp3")

            with st.expander("Raw session data (for debugging / handoff)"):
                st.json(st.session_state.get("db_payload", {}))