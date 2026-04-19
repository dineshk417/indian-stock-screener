"""
Global CSS for the Indian Stock Screener.

Import and call inject_global_css() at the top of every page (after
st.set_page_config) to apply consistent styling across the entire app.
"""
import streamlit as st

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

/* ── Base ─────────────────────────────────────────────────────────────────── */
html, body, [class*="css"], .stMarkdown, .stText {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}
h1 { font-weight: 800 !important; letter-spacing: -0.03em !important; font-size: 1.7rem !important; }
h2 { font-weight: 700 !important; letter-spacing: -0.02em !important; }
h3 { font-weight: 700 !important; letter-spacing: -0.01em !important; }

/* ── Layout ───────────────────────────────────────────────────────────────── */
.main .block-container {
    padding-top: 1.2rem !important;
    padding-bottom: 2rem !important;
    max-width: 1200px !important;
}
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }

/* ── Metric cards ─────────────────────────────────────────────────────────── */
[data-testid="metric-container"] {
    background: linear-gradient(145deg, #1a1f35 0%, #141828 100%) !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 14px !important;
    padding: 16px 20px !important;
    box-shadow: 0 2px 16px rgba(0,0,0,0.2) !important;
    transition: box-shadow 0.2s ease !important;
}
[data-testid="metric-container"]:hover {
    box-shadow: 0 4px 24px rgba(0,0,0,0.3) !important;
}
[data-testid="metric-container"] > label {
    color: #64748b !important;
    font-size: 0.67rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.5rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.03em !important;
    color: #f1f5f9 !important;
}
[data-testid="stMetricDelta"] {
    font-size: 0.8rem !important;
    font-weight: 600 !important;
}

/* ── Sidebar ──────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] > div:first-child {
    background: #0f1117 !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
}
[data-testid="stSidebar"] label {
    font-size: 0.67rem !important;
    font-weight: 700 !important;
    color: #64748b !important;
    text-transform: uppercase !important;
    letter-spacing: 0.09em !important;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    font-size: 0.85rem !important;
    color: #94a3b8 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
}

/* ── Buttons ──────────────────────────────────────────────────────────────── */
.stButton > button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    letter-spacing: 0.01em !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(0,0,0,0.3) !important;
}
.stButton > button[kind="primary"],
button[data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, #f0b429 0%, #d9971a 100%) !important;
    color: #0a0a0a !important;
    border: none !important;
    font-weight: 700 !important;
    box-shadow: 0 3px 12px rgba(240,180,41,0.2) !important;
}
.stButton > button[kind="primary"]:hover {
    box-shadow: 0 6px 20px rgba(240,180,41,0.35) !important;
}

/* ── Inputs / Selects ─────────────────────────────────────────────────────── */
[data-testid="stSelectbox"] > div > div,
[data-testid="stMultiSelect"] > div > div {
    border-radius: 10px !important;
    border-color: rgba(255,255,255,0.1) !important;
    background: rgba(255,255,255,0.03) !important;
}

/* ── Multiselect tags — kill the default salmon/red ──────────────────────── */
[data-baseweb="tag"] {
    background: rgba(124,131,253,0.14) !important;
    border: 1px solid rgba(124,131,253,0.32) !important;
    border-radius: 6px !important;
    padding: 2px 6px !important;
}
[data-baseweb="tag"] span {
    color: #a5b4fc !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
}
[data-baseweb="tag"] [role="presentation"] svg {
    fill: rgba(165,180,252,0.7) !important;
}

/* ── Number / text inputs ─────────────────────────────────────────────────── */
[data-testid="stNumberInput"] input,
[data-testid="stTextInput"]   input,
[data-testid="stTextArea"]    textarea {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 8px !important;
    color: #e2e8f0 !important;
    font-size: 0.88rem !important;
}
[data-testid="stNumberInput"] input:focus,
[data-testid="stTextInput"]   input:focus,
[data-testid="stTextArea"]    textarea:focus {
    border-color: rgba(240,180,41,0.5) !important;
    box-shadow: 0 0 0 2px rgba(240,180,41,0.1) !important;
}

/* ── Checkboxes ───────────────────────────────────────────────────────────── */
[data-testid="stCheckbox"] label span {
    font-size: 0.84rem !important;
    color: #94a3b8 !important;
}
[data-testid="stCheckbox"] input:checked + div {
    background: #f0b429 !important;
    border-color: #f0b429 !important;
}

/* ── Sliders ──────────────────────────────────────────────────────────────── */
[data-testid="stSlider"] [role="slider"] {
    background: #f0b429 !important;
    box-shadow: 0 0 0 4px rgba(240,180,41,0.2) !important;
}
[data-testid="stSlider"] [data-testid="stTickBarMin"],
[data-testid="stSlider"] [data-testid="stTickBarMax"] {
    color: #475569 !important;
    font-size: 0.72rem !important;
}

/* ── Download button ──────────────────────────────────────────────────────── */
[data-testid="stDownloadButton"] > button {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    color: #94a3b8 !important;
    border-radius: 8px !important;
    font-size: 0.82rem !important;
}
[data-testid="stDownloadButton"] > button:hover {
    border-color: rgba(240,180,41,0.4) !important;
    color: #f0b429 !important;
}

/* ── Selectbox dropdown options ───────────────────────────────────────────── */
[data-baseweb="popover"] [role="option"] {
    font-size: 0.84rem !important;
    color: #94a3b8 !important;
}
[data-baseweb="popover"] [role="option"]:hover,
[data-baseweb="popover"] [aria-selected="true"] {
    background: rgba(240,180,41,0.1) !important;
    color: #f0b429 !important;
}

/* ── DataFrames ───────────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: 12px !important;
    overflow: hidden !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
}
[data-testid="stDataFrame"] table thead th {
    background: #1a1f35 !important;
    color: #64748b !important;
    font-size: 0.7rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    border-bottom: 1px solid rgba(255,255,255,0.08) !important;
}
[data-testid="stDataFrame"] table tbody tr:hover {
    background: rgba(255,255,255,0.025) !important;
}

/* ── Expanders ────────────────────────────────────────────────────────────── */
details {
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 12px !important;
    overflow: hidden !important;
    background: #11151f !important;
}
details summary {
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    padding: 10px 14px !important;
    color: #94a3b8 !important;
    letter-spacing: 0.01em !important;
}
details summary:hover { color: #e2e8f0 !important; }

/* ── Tabs ─────────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [data-testid="stTab"] {
    font-weight: 600 !important;
    font-size: 0.83rem !important;
    letter-spacing: 0.01em !important;
    color: #64748b !important;
    border-radius: 8px 8px 0 0 !important;
    padding: 8px 16px !important;
}
[data-testid="stTabs"] [aria-selected="true"] {
    color: #f1f5f9 !important;
    border-bottom: 2px solid #f0b429 !important;
}

/* ── Alerts / banners ─────────────────────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 10px !important;
    border: none !important;
    font-size: 0.875rem !important;
}

/* ── Status widget ────────────────────────────────────────────────────────── */
[data-testid="stStatus"] {
    border-radius: 12px !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
}

/* ── Caption / small text ─────────────────────────────────────────────────── */
.stCaption, [data-testid="stCaptionContainer"] {
    color: #4b5563 !important;
    font-size: 0.78rem !important;
}

/* ── Dividers ─────────────────────────────────────────────────────────────── */
hr { border-color: rgba(255,255,255,0.06) !important; margin: 1rem 0 !important; }

/* ── Progress bars ────────────────────────────────────────────────────────── */
[data-testid="stProgressBar"] > div > div {
    background: linear-gradient(90deg, #f0b429, #00c896) !important;
    border-radius: 4px !important;
}

/* ── Page nav links — compact chip (main content) ─────────────────────────── */
a[data-testid="stPageLink-NavLink"] {
    display: inline-flex !important;
    align-items: center !important;
    width: auto !important;
    min-width: 0 !important;
    max-width: 100% !important;
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.09) !important;
    border-radius: 20px !important;
    padding: 5px 14px !important;
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    color: #64748b !important;
    letter-spacing: 0.02em !important;
    transition: color 0.15s ease, border-color 0.15s ease, background 0.15s ease !important;
    margin-bottom: 12px !important;
    box-shadow: none !important;
    transform: none !important;
}
a[data-testid="stPageLink-NavLink"]:hover {
    color: #f0b429 !important;
    border-color: rgba(240,180,41,0.35) !important;
    background: rgba(240,180,41,0.05) !important;
    transform: none !important;
    box-shadow: none !important;
}

/* ── Scrollbar ────────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }

/* ── Animations ───────────────────────────────────────────────────────────── */
@keyframes pulse {
    0%,100% { opacity: 1; }
    50%      { opacity: 0.35; }
}
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(5px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes slideIn {
    from { opacity: 0; transform: translateX(-8px); }
    to   { opacity: 1; transform: translateX(0); }
}

/* ── Spinner ──────────────────────────────────────────────────────────────── */
[data-testid="stSpinner"] { color: #f0b429 !important; }
</style>
"""


def inject_global_css() -> None:
    """Inject shared CSS. Call once, right after set_page_config."""
    st.markdown(_CSS, unsafe_allow_html=True)
