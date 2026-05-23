import streamlit as st


def score_gauge(label: str, score: float, color: str = "#2ecc71") -> None:
    bar_color = color if score >= 60 else ("#e67e22" if score >= 35 else "#e74c3c")
    st.markdown(
        f"""
        <div style="margin-bottom:8px">
            <div style="font-size:13px;color:#888;margin-bottom:4px">{label}</div>
            <div style="display:flex;align-items:center;gap:10px">
                <div style="flex:1;background:#2a2a2a;border-radius:6px;height:18px;overflow:hidden">
                    <div style="width:{score}%;background:{bar_color};height:100%;border-radius:6px;transition:width 0.4s"></div>
                </div>
                <span style="font-size:18px;font-weight:700;color:{bar_color};min-width:48px">{score}%</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def keyword_chips(keywords: list[str], color: str = "#2ecc71") -> None:
    if not keywords:
        return
    chips = "".join(
        f'<span style="background:{color}22;color:{color};border:1px solid {color}66;'
        f'border-radius:12px;padding:2px 10px;font-size:12px;margin:2px;display:inline-block">{kw}</span>'
        for kw in keywords
    )
    st.markdown(chips, unsafe_allow_html=True)


def section_header(title: str, subtitle: str = "") -> None:
    sub = f'<div style="font-size:13px;color:#888;margin-top:2px">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f'<div style="margin:16px 0 8px 0"><span style="font-size:17px;font-weight:600">{title}</span>{sub}</div>',
        unsafe_allow_html=True,
    )
