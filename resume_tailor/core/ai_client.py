import json
import os
import time
import streamlit as st
from groq import Groq, RateLimitError

_MODEL = "llama-3.3-70b-versatile"
_FAST_MODEL = "llama-3.1-8b-instant"  # higher rate limits, used for structured parsing


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


def _chat(system: str, user: str, temperature: float, max_tokens: int,
          model: str = _MODEL) -> str:
    api_key = _resolve_api_key()
    if not api_key:
        st.error(
            "**GROQ_API_KEY not set.** "
            "Paste your free key in the sidebar to continue. "
            "Get one at https://console.groq.com"
        )
        st.stop()
    client = get_client(api_key)
    for attempt in range(4):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except RateLimitError:
            if attempt == 3:
                st.error(
                    "Groq rate limit hit. Wait 30 seconds and try again, "
                    "or upgrade to a paid Groq plan for higher limits."
                )
                st.stop()
            wait = 2 ** (attempt + 2)   # 4s, 8s, 16s
            time.sleep(wait)


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
    user = (
        f"JOB DESCRIPTION:\n{jd_text}\n\n"
        f"ORIGINAL RESUME:\n{resume_text}\n\n"
        "Rewrite the resume to match the job description. Output the complete tailored resume only."
    )
    return _chat(system, user, temperature=0.3, max_tokens=3000)


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
    return _chat(system, user, temperature=0.5, max_tokens=800)


def parse_resume_to_structure(resume_text: str) -> dict:
    system = (
        "You are a resume parser. Convert a plain-text resume into a strict JSON structure.\n"
        "Output ONLY valid JSON — no prose, no markdown fences, no comments.\n\n"
        "Required schema:\n"
        '{"name":"Full Name","contact":["email","phone","location","linkedin"],'
        '"summary":"summary text or empty string","sections":['
        '{"title":"Experience","type":"entries","entries":[{"role":"","org":"","duration":"","location":"","bullets":[]}]},'
        '{"title":"Skills","type":"skills","categories":[{"label":"Languages","items":"Python, SQL"}]},'
        '{"title":"Education","type":"entries","entries":[{"role":"Degree","org":"University","duration":"","location":"","bullets":[]}]}'
        "]}\n\n"
        "Rules:\n"
        "- type='entries' for Experience, Education, Projects, Certifications.\n"
        "- type='skills' for Skills sections; group into concise categories.\n"
        "- type='text' with 'content' key for any other section.\n"
        "- Preserve bullet text exactly. Empty string for unknown fields, never omit keys."
    )
    user = f"Parse this resume:\n\n{resume_text}"
    raw = _chat(system, user, temperature=0.1, max_tokens=2500, model=_FAST_MODEL)
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        return json.loads(raw[start:end])
    except Exception:
        return {"name": "", "contact": [], "summary": resume_text, "sections": []}


def incorporate_keywords(resume_text: str, missing_keywords: list[str]) -> str:
    kw_list = ", ".join(missing_keywords)
    system = (
        "You are an expert resume writer. Integrate missing keywords into an existing resume naturally.\n\n"
        "Rules:\n"
        "- Only add keywords plausible given the candidate's existing background.\n"
        "- Weave them into existing bullets, the skills section, or the summary — never invent experience.\n"
        "- Skip keywords that cannot be added credibly.\n"
        "- Preserve all section headers, formatting, and original content.\n"
        "- Output ONLY the updated resume text — no preamble, no commentary."
    )
    user = (
        f"MISSING KEYWORDS:\n{kw_list}\n\n"
        f"CURRENT RESUME:\n{resume_text}\n\n"
        "Integrate the keywords naturally. Output the complete updated resume only."
    )
    return _chat(system, user, temperature=0.3, max_tokens=3000)


def extract_ats_keywords(jd_text: str) -> list[str]:
    system = "You are an ATS specialist. Extract important keywords from job descriptions."
    user = (
        "Extract the top 30–40 ATS keywords from the job description below.\n"
        "Include: skills, tools, technologies, certifications, methodologies, role-specific terms.\n"
        "Exclude: company name, generic words, stop words.\n"
        'Output ONLY a JSON array of lowercase strings. No prose, no fences.\n'
        'Example: ["python", "machine learning", "aws", "sql", "agile"]\n\n'
        f"JOB DESCRIPTION:\n{jd_text}"
    )
    raw = _chat(system, user, temperature=0.1, max_tokens=400, model=_FAST_MODEL)
    try:
        start = raw.find("[")
        end = raw.rfind("]") + 1
        return json.loads(raw[start:end]) if start != -1 else []
    except (json.JSONDecodeError, ValueError):
        return []
