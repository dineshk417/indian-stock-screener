"""
User Analytics — shows who is using NiftyEdge.
Visible to any logged-in user; full detail gated to ADMIN_EMAIL in secrets.
"""
import streamlit as st
import pandas as pd
import datetime as _dt

st.set_page_config(page_title="Users · NiftyEdge", layout="wide", page_icon="👥")
from ui.styles import inject_global_css, page_header, auth_guard, user_sidebar, theme_toggle
inject_global_css()
auth_guard()

with st.sidebar:
    theme_toggle()
    st.divider()
    user_sidebar()

page_header("👥 User Analytics", subtitle="NiftyEdge · Registered Users", badge="ADMIN")

# ── Admin gate ──────────────────────────────────────────────────────────────────────────
try:
    admin_email = st.secrets.get("ADMIN_EMAIL", "") or ""
except Exception:
    admin_email = ""

is_admin = (not admin_email) or (st.user.email == admin_email)

if not is_admin:
    st.markdown(
        '<div style="background:rgba(255,77,109,0.06);border:1px solid rgba(255,77,109,0.2);'
        'border-left:4px solid #ff4d6d;border-radius:12px;padding:20px 24px;margin-top:24px;">'
        '<div style="color:#ff4d6d;font-weight:700;font-size:1rem;margin-bottom:6px;">'
        '🔒 Access Restricted</div>'
        '<div style="color:#64748b;font-size:0.84rem;">This page is for NiftyEdge administrators only.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.stop()

# ── Load users ──────────────────────────────────────────────────────────────────────────
try:
    from auth.user_store import get_all_users
    users = get_all_users()
except Exception as e:
    st.error(f"Could not load users: {e}")
    st.stop()

if not users:
    st.info("No users have signed in yet. Share the app and they'll appear here after their first login.")
    st.stop()

df = pd.DataFrame(users)

# ── KPIs ──────────────────────────────────────────────────────────────────────────────
total        = len(df)
total_visits = int(df["visit_count"].sum())

# Active today
try:
    today_str = _dt.date.today().isoformat()
    active_today = int(df["last_seen"].str.startswith(today_str).sum())
except Exception:
    active_today = 0

# New this week
try:
    week_ago = (_dt.datetime.utcnow() - _dt.timedelta(days=7)).isoformat()
    new_week = int((df["first_seen"] >= week_ago).sum())
except Exception:
    new_week = 0

def _kpi(label, value, sub="", color="#3b82f6"):
    return (
        f'<div style="background:linear-gradient(145deg,#1a1f35,#141828);'
        f'border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:16px 18px;">'
        f'<div style="color:#64748b;font-size:0.6rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.09em;margin-bottom:6px;">{label}</div>'
        f'<div style="color:{color};font-size:1.8rem;font-weight:800;">{value}</div>'
        f'<div style="color:#475569;font-size:0.7rem;margin-top:3px;">{sub}</div>'
        f'</div>'
    )

st.markdown(
    f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:24px;">'
    + _kpi("Total Users",     str(total),        "all time", "#3b82f6")
    + _kpi("Active Today",    str(active_today),  "unique visitors", "#22c55e")
    + _kpi("New This Week",   str(new_week),      "first-time signins", "#f59e0b")
    + _kpi("Total Sessions",  str(total_visits),  "cumulative visits", "#8b5cf6")
    + "</div>",
    unsafe_allow_html=True,
)

# ── User table ───────────────────────────────────────────────────────────────────────────
st.markdown(
    '<div style="font-size:0.72rem;font-weight:700;color:#64748b;'
    'text-transform:uppercase;letter-spacing:0.09em;margin-bottom:12px;">All Users</div>',
    unsafe_allow_html=True,
)

show = df[["name", "email", "provider", "first_seen", "last_seen", "visit_count"]].copy()
show.columns = ["Name", "Email", "Provider", "First Seen", "Last Seen", "Sessions"]

for col in ("First Seen", "Last Seen"):
    show[col] = pd.to_datetime(show[col], errors="coerce").dt.strftime("%d %b %Y %H:%M UTC")

show["Sessions"] = show["Sessions"].astype(int)

def _sessions_style(v):
    if v >= 20: return "color:#22c55e;font-weight:700"
    if v >= 5:  return "color:#f59e0b;font-weight:600"
    return "color:#94a3b8"

styled = show.style.map(_sessions_style, subset=["Sessions"])
st.dataframe(styled, use_container_width=True, height=480, hide_index=True)

csv = df.to_csv(index=False).encode()
st.download_button(
    "⬇ Download CSV",
    csv,
    file_name=f"niftyedge_users_{_dt.date.today()}.csv",
    mime="text/csv",
)
