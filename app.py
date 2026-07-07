import streamlit as st
import uuid
import requests
import html
from audio_recorder_streamlit import audio_recorder

BACKEND_URL = "http://localhost:8000"

st.set_page_config(page_title="AI Mock Interview - Velira", page_icon="🤖")

# ============================================================
# VISUAL THEME
# Palette: ink #1B1F23, paper #FAFAF8, teal #0F6E6E, mist #E7EEEC, coral #E8535B
# Display font: Space Grotesk (headings, labels) — body stays Streamlit's default
# Signature element: the stage stepper below, which mirrors the real state machine
# ============================================================
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&display=swap');

h1, h2, h3, .stepper .step-label {
    font-family: 'Space Grotesk', sans-serif !important;
}

h1 { letter-spacing: -0.01em; }

/* ── Stage stepper ───────────────────────────────────────── */
.stepper {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin: 0.5rem 0 1.75rem 0;
}
.step { display: flex; flex-direction: column; align-items: center; flex: 0 0 auto; }
.step .dot {
    width: 16px; height: 16px; border-radius: 50%;
    border: 2px solid #E7EEEC; background: #FAFAF8;
    margin-top: 4px;
}
.step.done .dot { background: #0F6E6E; border-color: #0F6E6E; }
.step.current .dot {
    background: #FAFAF8; border-color: #0F6E6E;
    box-shadow: 0 0 0 4px rgba(15, 110, 110, 0.15);
}
.step .step-label {
    font-size: 0.7rem; margin-top: 6px; color: #1B1F23; opacity: 0.5;
    text-transform: uppercase; letter-spacing: 0.06em; white-space: nowrap;
}
.step.current .step-label, .step.done .step-label { opacity: 1; font-weight: 700; }
.stepper-line { flex: 1 1 auto; height: 2px; background: #E7EEEC; margin: 12px 4px 0 4px; }
.stepper-line.done { background: #0F6E6E; }

/* ── Chat bubbles ─────────────────────────────────────────── */
.bubble-row { display: flex; margin: 0.35rem 0; }
.velira-row { justify-content: flex-start; }
.candidate-row { justify-content: flex-end; }
.bubble-label {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.06em;
    opacity: 0.6; margin-bottom: 0.2rem;
}
.velira-bubble {
    background: #E7EEEC; border-radius: 14px 14px 14px 2px;
    padding: 0.7rem 1rem; max-width: 80%; line-height: 1.45;
}
.velira-bubble.flagged {
    background: rgba(232, 83, 91, 0.10);
    border: 1px solid rgba(232, 83, 91, 0.4);
}
.candidate-bubble {
    background: #0F6E6E; color: #FAFAF8; border-radius: 14px 14px 2px 14px;
    padding: 0.7rem 1rem; max-width: 80%; line-height: 1.45;
}
.candidate-bubble .bubble-label { color: #FAFAF8; opacity: 0.75; }

/* ── Buttons ──────────────────────────────────────────────── */
.stButton > button {
    border-radius: 8px;
    font-weight: 600;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def render_stepper(current_state: str, complete: bool):
    """Renders the interview's 5 stages as a horizontal progress stepper."""
    stages = ["warmup", "technical", "probing", "wrapup", "completed"]
    labels = {
        "warmup": "Warm-up",
        "technical": "Technical",
        "probing": "Probing",
        "wrapup": "Wrap-up",
        "completed": "Complete",
    }
    effective_state = "completed" if complete else current_state
    current_index = stages.index(effective_state) if effective_state in stages else 0

    parts = ['<div class="stepper">']
    for i, stage in enumerate(stages):
        if i < current_index or (complete and i <= current_index):
            step_class = "step done"
        elif i == current_index:
            step_class = "step current"
        else:
            step_class = "step pending"
        parts.append(f'<div class="{step_class}"><div class="dot"></div><div class="step-label">{labels[stage]}</div></div>')
        if i < len(stages) - 1:
            line_class = "stepper-line done" if i < current_index else "stepper-line"
            parts.append(f'<div class="{line_class}"></div>')
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def escape_for_bubble(text: str) -> str:
    """Escapes HTML special characters and preserves line breaks for chat bubbles."""
    return html.escape(text).replace("\n", "<br>")


st.title("🤖💻 AI Mock Interview Simulator")

# Keep a stable session_id for this browser session
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# Tracks whether the interview has been started against the backend
if "interview_started" not in st.session_state:
    st.session_state.interview_started = False

st.caption(f"Session ID: {st.session_state.session_id}")

if not st.session_state.interview_started:
    entry_mode = st.radio(
        "How would you like to start?",
        ["Fill form manually", "Upload resume (PDF)"],
        horizontal=True,
    )
else:
    entry_mode = None

# ============================================================
# ENTRY MODE 1 — MANUAL PROFILE FORM
# ============================================================
if entry_mode == "Fill form manually":
    with st.form("profile_form"):
        st.subheader("Candidate Profile")

        candidate_name = st.text_input("Full Name", placeholder="e.g. Shrishti")

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
            company_type = st.selectbox("Company Style", ["General", "Startup"])
        with col4:
            interview_tone = st.selectbox("Interview Tone", ["Friendly", "Direct", "Strict"])

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
# ENTRY MODE 2 — RESUME UPLOAD
# ============================================================
if entry_mode == "Upload resume (PDF)":
    st.subheader("Upload Resume")
    st.caption(
        "Gemini will extract your name, domain, skills, experience, education, "
        "projects and certifications directly from the PDF."
    )

    resume_file = st.file_uploader("Resume (PDF only)", type=["pdf"])

    col5, col6 = st.columns(2)
    with col5:
        upload_company_type = st.selectbox(
            "Company Style", ["General", "Startup", "FAANG"], key="upload_company_type"
        )
    with col6:
        upload_interview_tone = st.selectbox(
            "Interview Tone", ["Friendly", "Direct", "Stressful"], key="upload_interview_tone"
        )

    upload_clicked = st.button("Start Interview from Resume")

    if upload_clicked:
        if resume_file is None:
            st.error("Please upload a PDF resume first.")
        else:
            with st.spinner("Extracting resume and starting interview..."):
                try:
                    upload_response = requests.post(
                        f"{BACKEND_URL}/upload-resume-and-start",
                        files={
                            "file": (resume_file.name, resume_file.getvalue(), "application/pdf")
                        },
                        data={
                            "company_type": upload_company_type,
                            "interview_tone": upload_interview_tone,
                        },
                        timeout=90,
                    )
                except requests.exceptions.ConnectionError:
                    st.error(
                        "Could not reach the backend at "
                        f"{BACKEND_URL}. Make sure the backend is still running."
                    )
                    upload_response = None

            if upload_response is not None:
                if upload_response.status_code == 200:
                    data = upload_response.json()

                    # IMPORTANT: this endpoint generates its OWN session_id
                    # internally — we must adopt whatever it returns, or the
                    # next /reply call will 404 with "Session not found."
                    st.session_state.session_id = data["session_id"]

                    st.session_state.interview_started = True
                    st.session_state.current_state = "warmup"
                    st.session_state.interview_complete = False
                    st.session_state.profile = {
                        "candidate_name": data.get("candidate_name", "Candidate")
                    }
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
                    st.error(f"Backend error ({upload_response.status_code}): {upload_response.text}")

# ============================================================
# INTERVIEW LOOP — shows transcript so far + lets candidate reply
# ============================================================
if st.session_state.interview_started:
    st.divider()
    render_stepper(
        st.session_state.get("current_state", "warmup"),
        st.session_state.get("interview_complete", False),
    )

    transcript = st.session_state.get("transcript", [])

    # Render the full conversation so far, as chat bubbles
    for i, turn in enumerate(transcript):
        is_last = (i == len(transcript) - 1)
        if turn["role"] == "velira":
            flagged = turn.get("flagged", False)
            bubble_class = "velira-bubble flagged" if flagged else "velira-bubble"
            label = "Velira · guardrail" if flagged else "Velira"
            st.markdown(
                f'<div class="bubble-row velira-row"><div class="{bubble_class}">'
                f'<div class="bubble-label">{label}</div>{escape_for_bubble(turn["text"])}'
                f'</div></div>',
                unsafe_allow_html=True,
            )
            # Only fetch/play audio for the most recent Velira message,
            # to avoid re-downloading every clip on every rerun
            if is_last and turn.get("audio"):
                audio_response = requests.get(f"{BACKEND_URL}/audio/{turn['audio']}")
                if audio_response.status_code == 200:
                    st.audio(audio_response.content, format="audio/mp3")
                else:
                    st.warning("Could not load audio for this message.")
        else:
            st.markdown(
                f'<div class="bubble-row candidate-row"><div class="candidate-bubble">'
                f'<div class="bubble-label">You</div>{escape_for_bubble(turn["text"])}'
                f'</div></div>',
                unsafe_allow_html=True,
            )

    st.write("")

    # ── Candidate reply form (only while interview is still running) ──────
    if not st.session_state.get("interview_complete"):

        # ── Voice input: record, transcribe via /transcribe, fill answer box ──
        st.write("**Speak your answer** (optional — or just type below)")
        audio_bytes = audio_recorder(
            text="",
            recording_color="#e8535b",
            neutral_color="#6c757d",
            icon_size="2x",
            key="answer_recorder",
        )

        if audio_bytes:
            st.audio(audio_bytes, format="audio/wav")
            if st.button("Use this recording as my answer"):
                with st.spinner("Transcribing..."):
                    try:
                        stt_response = requests.post(
                            f"{BACKEND_URL}/transcribe",
                            files={"audio": ("recording.wav", audio_bytes, "audio/wav")},
                            timeout=60,
                        )
                    except requests.exceptions.ConnectionError:
                        st.error(
                            "Could not reach the backend at "
                            f"{BACKEND_URL}. Make sure the backend is still running."
                        )
                        stt_response = None

                if stt_response is not None:
                    if stt_response.status_code == 200:
                        transcript = stt_response.json().get("transcript", "")
                        # Pre-fill the answer box below with the transcribed text
                        st.session_state["candidate_answer_input"] = transcript
                        st.success(f"Transcribed: {transcript}")
                        st.rerun()
                    else:
                        st.error(f"Backend error ({stt_response.status_code}): {stt_response.text}")

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

        # ── End Interview Early (right-aligned, always visible) ────────────
        st.divider()
        spacer_col, button_col = st.columns([4, 1])
        with button_col:
            end_early_clicked = st.button(
                "End Interview Early",
                type="secondary",
                use_container_width=True,
                help="Closes the session now. No scored feedback report — only the transcript so far.",
            )

        if end_early_clicked:
            with st.spinner("Closing session..."):
                try:
                    close_response = requests.post(
                        f"{BACKEND_URL}/session-close",
                        params={"session_id": st.session_state.session_id},
                        timeout=30,
                    )
                except requests.exceptions.ConnectionError:
                    st.error(
                        "Could not reach the backend at "
                        f"{BACKEND_URL}. Make sure the backend is still running."
                    )
                    close_response = None

            if close_response is not None:
                if close_response.status_code == 200:
                    close_data = close_response.json()
                    st.session_state.interview_complete = True
                    st.session_state.ended_early = True
                    st.session_state.db_payload = close_data.get("db_payload")
                    st.session_state.close_warning = close_data.get("warning")
                    st.rerun()
                else:
                    st.error(f"Backend error ({close_response.status_code}): {close_response.text}")
    elif st.session_state.get("ended_early"):
        st.warning(st.session_state.get("close_warning") or "Interview ended early — no feedback report available.")
        with st.expander("Transcript / session data collected so far", expanded=True):
            st.json(st.session_state.get("db_payload", {}))
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
