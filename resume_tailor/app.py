import os
from dotenv import load_dotenv
import streamlit as st

from core.extractor import extract_text_from_upload
from core.ai_client import tailor_resume, generate_cover_letter, extract_ats_keywords
from core.ats_scorer import compute_ats_scores
from core.docx_builder import text_to_docx_bytes
from core.scraper import scrape_job_url
from ui.components import score_gauge, keyword_chips, section_header

load_dotenv()

st.set_page_config(
    page_title="Resume Tailor",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.title("📄 Resume Tailor")
st.caption("Upload your resume + paste/upload/link a job description — get a tailored resume, cover letter & ATS score.")

tab_inputs, tab_resume, tab_cover = st.tabs(["📥 Inputs", "✏️ Tailored Resume", "📝 Cover Letter"])

with tab_inputs:
    col_left, col_right = st.columns(2, gap="large")

    with col_left:
        section_header("Your Resume")
        resume_mode = st.radio(
            "Resume input", ["Paste text", "Upload file"],
            key="resume_mode", horizontal=True, label_visibility="collapsed",
        )
        if resume_mode == "Paste text":
            st.text_area("Paste your resume here", height=380, key="resume_text",
                         placeholder="Paste your full resume text…")
        else:
            st.file_uploader("Upload resume (PDF or DOCX)", type=["pdf", "docx"], key="resume_file")

    with col_right:
        section_header("Job Description")
        jd_mode = st.radio(
            "JD input", ["Paste text", "Upload file", "Job URL (LinkedIn / any)"],
            key="jd_mode", horizontal=True, label_visibility="collapsed",
        )
        if jd_mode == "Paste text":
            st.text_area("Paste the job description here", height=300, key="jd_text",
                         placeholder="Paste the full job description…")
        elif jd_mode == "Upload file":
            st.file_uploader("Upload job description (PDF or DOCX)", type=["pdf", "docx"], key="jd_file")
        else:
            st.text_input(
                "Job posting URL",
                key="jd_url",
                placeholder="https://www.linkedin.com/jobs/view/… or any job page URL",
            )
            st.caption("Works with LinkedIn, Naukri, Indeed, company career pages, etc. "
                       "If the page requires login, paste the text instead.")
        st.text_input("Company name (optional)", key="company_name", placeholder="e.g. Google")

    st.divider()
    if st.button("🚀 Tailor My Resume", type="primary", use_container_width=True):
        try:
            if resume_mode == "Upload file":
                f = st.session_state.get("resume_file")
                if not f:
                    st.error("Please upload your resume file.")
                    st.stop()
                resume_text = extract_text_from_upload(f)
            else:
                resume_text = (st.session_state.get("resume_text") or "").strip()
                if not resume_text:
                    st.error("Please paste your resume text.")
                    st.stop()
        except Exception as e:
            st.error(f"Could not read resume: {e}")
            st.stop()

        try:
            if jd_mode == "Upload file":
                f = st.session_state.get("jd_file")
                if not f:
                    st.error("Please upload the job description file.")
                    st.stop()
                jd_text = extract_text_from_upload(f)
            elif jd_mode == "Job URL (LinkedIn / any)":
                url = (st.session_state.get("jd_url") or "").strip()
                if not url:
                    st.error("Please enter a job posting URL.")
                    st.stop()
                with st.spinner("Fetching job description from URL…"):
                    jd_text, warn = scrape_job_url(url)
                if warn:
                    st.warning(warn)
                    st.stop()
            else:
                jd_text = (st.session_state.get("jd_text") or "").strip()
                if not jd_text:
                    st.error("Please paste the job description.")
                    st.stop()
        except Exception as e:
            st.error(f"Could not read job description: {e}")
            st.stop()

        company = st.session_state.get("company_name", "")

        with st.spinner("Extracting ATS keywords…"):
            keywords = extract_ats_keywords(jd_text)

        with st.spinner("Tailoring your resume… (this takes ~15 seconds)"):
            tailored = tailor_resume(resume_text, jd_text)

        with st.spinner("Writing cover letter…"):
            cover = generate_cover_letter(resume_text, jd_text, company)

        ats = compute_ats_scores(resume_text, tailored, keywords)

        st.session_state.update({
            "resume_raw": resume_text,
            "jd_raw": jd_text,
            "tailored_resume": tailored,
            "cover_letter": cover,
            "jd_keywords": keywords,
            "ats_scores": ats,
        })
        st.success("✅ Done! Switch to the **Tailored Resume** or **Cover Letter** tabs.")

with tab_resume:
    if "tailored_resume" not in st.session_state:
        st.info("Complete the inputs and click **Tailor My Resume** to see results here.")
    else:
        ats = st.session_state["ats_scores"]
        section_header("ATS Keyword Match Score", "How well your resume matches the job description")
        g1, g2 = st.columns(2)
        with g1:
            score_gauge("Before tailoring", ats["before"]["score"])
        with g2:
            score_gauge("After tailoring", ats["after"]["score"], color="#27ae60")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**✅ Matched keywords**")
            keyword_chips(ats["after"]["matched"], "#2ecc71")
        with c2:
            st.markdown("**❌ Missing keywords**")
            keyword_chips(ats["after"]["missing"], "#e74c3c")

        st.divider()
        section_header("Tailored Resume", "Edit below before downloading")
        edited_resume = st.text_area(
            "Tailored resume", value=st.session_state["tailored_resume"],
            height=600, key="edited_resume", label_visibility="collapsed",
        )
        st.download_button(
            "⬇️ Download Tailored Resume (.docx)",
            data=text_to_docx_bytes(edited_resume, title="Tailored Resume"),
            file_name="tailored_resume.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )

with tab_cover:
    if "cover_letter" not in st.session_state:
        st.info("Complete the inputs and click **Tailor My Resume** to see results here.")
    else:
        section_header("Cover Letter", "Edit below before downloading")
        edited_cover = st.text_area(
            "Cover letter", value=st.session_state["cover_letter"],
            height=450, key="edited_cover", label_visibility="collapsed",
        )
        st.download_button(
            "⬇️ Download Cover Letter (.docx)",
            data=text_to_docx_bytes(edited_cover, title="Cover Letter"),
            file_name="cover_letter.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )

with st.sidebar:
    st.markdown("### Resume Tailor")
    st.caption("Powered by Groq · llama-3.3-70b · Free")
    with st.expander("How it works"):
        st.markdown(
            "1. Upload or paste your resume.\n"
            "2. Paste, upload, or drop a LinkedIn/job URL.\n"
            "3. The AI rewrites your resume to mirror the JD's exact terminology.\n"
            "4. ATS score shows keyword match before and after.\n"
            "5. A tailored cover letter is generated automatically.\n"
            "6. Download both as editable .docx files."
        )
    st.markdown("---")
    st.markdown("[Get a free Groq API key →](https://console.groq.com)")
