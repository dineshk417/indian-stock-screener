import os
from dotenv import load_dotenv
import streamlit as st

from core.extractor import extract_text_from_upload
from core.ai_client import tailor_resume, generate_cover_letter, extract_ats_keywords
from core.ats_scorer import compute_ats_scores
from core.docx_builder import text_to_docx_bytes
from ui.components import score_gauge, keyword_chips, section_header

load_dotenv()

st.set_page_config(
    page_title="Resume Tailor",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.title("📄 Resume Tailor")
st.caption("Paste or upload your resume + a job description — get a tailored resume, cover letter, and ATS score instantly.")

tab_inputs, tab_resume, tab_cover = st.tabs(["📥 Inputs", "✏️ Tailored Resume", "📝 Cover Letter"])

with tab_inputs:
    col_left, col_right = st.columns(2, gap="large")

    with col_left:
        section_header("Your Resume")
        resume_mode = st.radio("Input method", ["Paste text", "Upload file"], key="resume_mode", horizontal=True, label_visibility="collapsed")
        if resume_mode == "Paste text":
            resume_input = st.text_area("Paste your resume here", height=380, key="resume_text", placeholder="Paste your full resume text…")
        else:
            resume_file = st.file_uploader("Upload resume (PDF or DOCX)", type=["pdf", "docx"], key="resume_file")
            resume_input = None

    with col_right:
        section_header("Job Description")
        jd_mode = st.radio("Input method", ["Paste text", "Upload file"], key="jd_mode", horizontal=True, label_visibility="collapsed")
        if jd_mode == "Paste text":
            jd_input = st.text_area("Paste the job description here", height=320, key="jd_text", placeholder="Paste the full job description…")
        else:
            jd_file = st.file_uploader("Upload job description (PDF or DOCX)", type=["pdf", "docx"], key="jd_file")
            jd_input = None
        company_name = st.text_input("Company name (optional)", key="company_name", placeholder="e.g. Google")

    st.divider()
    if st.button("🚀 Tailor My Resume", type="primary", use_container_width=True):
        try:
            if resume_mode == "Upload file":
                if not st.session_state.get("resume_file"):
                    st.error("Please upload your resume file.")
                    st.stop()
                resume_text = extract_text_from_upload(st.session_state["resume_file"])
            else:
                resume_text = (st.session_state.get("resume_text") or "").strip()
                if not resume_text:
                    st.error("Please paste your resume text.")
                    st.stop()

            if jd_mode == "Upload file":
                if not st.session_state.get("jd_file"):
                    st.error("Please upload the job description file.")
                    st.stop()
                jd_text = extract_text_from_upload(st.session_state["jd_file"])
            else:
                jd_text = (st.session_state.get("jd_text") or "").strip()
                if not jd_text:
                    st.error("Please paste the job description.")
                    st.stop()
        except Exception as e:
            st.error(f"Failed to read file: {e}")
            st.stop()

        company = st.session_state.get("company_name", "")

        with st.spinner("Extracting ATS keywords…"):
            keywords = extract_ats_keywords(jd_text)

        with st.spinner("Tailoring your resume…"):
            tailored = tailor_resume(resume_text, jd_text)

        with st.spinner("Writing cover letter…"):
            cover = generate_cover_letter(resume_text, jd_text, company)

        ats = compute_ats_scores(resume_text, tailored, keywords)

        st.session_state["resume_raw"] = resume_text
        st.session_state["jd_raw"] = jd_text
        st.session_state["tailored_resume"] = tailored
        st.session_state["cover_letter"] = cover
        st.session_state["jd_keywords"] = keywords
        st.session_state["ats_scores"] = ats

        st.success("Done! Switch to the **Tailored Resume** or **Cover Letter** tabs.")

with tab_resume:
    if "tailored_resume" not in st.session_state:
        st.info("Fill in your resume and job description in the **Inputs** tab, then click **Tailor My Resume**.")
    else:
        ats = st.session_state["ats_scores"]
        before = ats["before"]
        after = ats["after"]

        section_header("ATS Keyword Match Score", "How well your resume matches the job description")
        g1, g2 = st.columns(2)
        with g1:
            score_gauge("Before tailoring", before["score"])
        with g2:
            score_gauge("After tailoring", after["score"], color="#27ae60")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Matched keywords**")
            keyword_chips(after["matched"], "#2ecc71")
        with c2:
            st.markdown("**Missing keywords**")
            keyword_chips(after["missing"], "#e74c3c")

        st.divider()
        section_header("Tailored Resume", "Edit below before downloading")
        edited_resume = st.text_area(
            "Tailored resume",
            value=st.session_state["tailored_resume"],
            height=600,
            key="edited_resume",
            label_visibility="collapsed",
        )
        st.download_button(
            "⬇️ Download as .docx",
            data=text_to_docx_bytes(edited_resume, title="Tailored Resume"),
            file_name="tailored_resume.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

with tab_cover:
    if "cover_letter" not in st.session_state:
        st.info("Fill in your resume and job description in the **Inputs** tab, then click **Tailor My Resume**.")
    else:
        section_header("Cover Letter", "Edit below before downloading")
        edited_cover = st.text_area(
            "Cover letter",
            value=st.session_state["cover_letter"],
            height=450,
            key="edited_cover",
            label_visibility="collapsed",
        )
        st.download_button(
            "⬇️ Download as .docx",
            data=text_to_docx_bytes(edited_cover, title="Cover Letter"),
            file_name="cover_letter.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

with st.sidebar:
    st.markdown("### Resume Tailor v1.0")
    st.caption("Powered by Groq · llama-3.3-70b")
    with st.expander("How it works"):
        st.markdown(
            "1. Paste or upload your resume and the target job description.\n"
            "2. The AI rewrites your resume to mirror JD terminology and prioritise relevant experience.\n"
            "3. ATS score shows keyword coverage before and after tailoring.\n"
            "4. A matching cover letter is generated automatically.\n"
            "5. Download both as editable .docx files."
        )
    st.markdown("---")
    st.markdown("[Get a free Groq API key →](https://console.groq.com)")
