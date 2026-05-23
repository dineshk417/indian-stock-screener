import json
import os
import streamlit as st
from groq import Groq

_MODEL = "llama-3.3-70b-versatile"


def _resolve_api_key() -> str:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        try:
            key = st.secrets["GROQ_API_KEY"]
        except Exception:
            pass
    if not key:
        key = st.session_state.get("_groq_key", "")
    return key.strip()


@st.cache_resource
def get_client(api_key: str) -> Groq:
    return Groq(api_key=api_key)


def _chat(system: str, user: str, temperature: float, max_tokens: int) -> str:
    api_key = _resolve_api_key()
    if not api_key:
        st.error(
            "**GROQ_API_KEY not set.** "
            "Paste your free key in the sidebar to continue. "
            "Get one at https://console.groq.com"
        )
        st.stop()
    client = get_client(api_key)
    response = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


def tailor_resume(resume_text: str, jd_text: str) -> str:
    system = (
        "You are an expert technical resume writer. "
        "Rewrite the provided resume to target the given job description.\n\n"
        "Rules:\n"
        "- Keep all facts accurate — never fabricate experience or qualifications.\n"
        "- Mirror the exact terminology, skill names, and action verbs used in the JD.\n"
        "- Reorder bullets so the most JD-relevant achievements appear first.\n"
        "- Use strong action verbs and quantified impact where the original has data.\n"
        "- Preserve all section headers (Summary, Experience, Education, Skills, etc.).\n"
        "- Output ONLY the resume text — no preamble, no commentary, no markdown fences."
    )
    user = f"JOB DESCRIPTION:\n{jd_text}\n\nORIGINAL RESUME:\n{resume_text}\n\nRewrite the resume to match the job description. Output the complete tailored resume only."
    return _chat(system, user, temperature=0.3, max_tokens=4096)


def generate_cover_letter(resume_text: str, jd_text: str, company_name: str) -> str:
    company_note = f"Company name: {company_name}" if company_name.strip() else "Company name not provided."
    system = (
        "You are a professional career coach writing cover letters.\n\n"
        "Rules:\n"
        "- Four paragraphs: hook, evidence, cultural fit, call to action.\n"
        "- Reference specific requirements from the JD by name.\n"
        "- Use concrete achievements from the resume as evidence.\n"
        "- Never use generic phrases like 'I am a passionate team player'.\n"
        "- Output ONLY the cover letter body — no subject line, no 'Dear Hiring Manager' header.\n"
        "- Plain text only, no markdown."
    )
    user = f"JOB DESCRIPTION:\n{jd_text}\n\nRESUME:\n{resume_text}\n\n{company_note}\n\nWrite the cover letter body."
    return _chat(system, user, temperature=0.5, max_tokens=1024)


def incorporate_keywords(resume_text: str, missing_keywords: list[str]) -> str:
    kw_list = ", ".join(missing_keywords)
    system = (
        "You are an expert resume writer. Your task is to integrate missing keywords "
        "into an existing resume naturally and credibly.\n\n"
        "Rules:\n"
        "- Only add keywords that are genuinely plausible given the candidate's existing background.\n"
        "- Weave keywords into existing bullet points, the skills section, or the summary — do not invent fake jobs or fake experience.\n"
        "- If a keyword cannot be added credibly, skip it silently.\n"
        "- Preserve all section headers, formatting, and original content.\n"
        "- Output ONLY the updated resume text — no preamble, no commentary."
    )
    user = (
        f"MISSING KEYWORDS TO INCORPORATE:\n{kw_list}\n\n"
        f"CURRENT RESUME:\n{resume_text}\n\n"
        "Integrate as many of the missing keywords as possible into the resume naturally. "
        "Output the complete updated resume only."
    )
    return _chat(system, user, temperature=0.3, max_tokens=4096)


def extract_ats_keywords(jd_text: str) -> list[str]:
    system = "You are an ATS (Applicant Tracking System) specialist. Extract important keywords from job descriptions."
    user = (
        "Extract the top 30–40 ATS keywords from the job description below.\n"
        "Include: required skills, tools, technologies, certifications, methodologies, role-specific terminology.\n"
        "Exclude: company name, generic words (team, work, company), and stop words.\n"
        'Output ONLY a JSON array of lowercase strings. No prose, no fences.\n'
        'Example: ["python", "machine learning", "aws", "sql", "agile"]\n\n'
        f"JOB DESCRIPTION:\n{jd_text}"
    )
    raw = _chat(system, user, temperature=0.1, max_tokens=512)
    try:
        start = raw.find("[")
        end = raw.rfind("]") + 1
        return json.loads(raw[start:end]) if start != -1 else []
    except (json.JSONDecodeError, ValueError):
        return []
