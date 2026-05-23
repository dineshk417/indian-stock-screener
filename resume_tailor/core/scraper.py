import re
import requests
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _extract_linkedin(soup: BeautifulSoup) -> str:
    selectors = [
        "div.description__text",
        "div.show-more-less-html__markup",
        "section.description",
        "div[class*='description']",
    ]
    for sel in selectors:
        el = soup.select_one(sel)
        if el and len(el.get_text(strip=True)) > 100:
            return el.get_text(separator="\n", strip=True)

    meta = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", property="og:description"
    )
    if meta and meta.get("content"):
        return meta["content"]
    return ""


def _extract_generic(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()

    candidates = soup.find_all(
        ["article", "main", "section", "div"],
        class_=re.compile(r"job|description|posting|content|detail", re.I),
    )
    if candidates:
        best = max(candidates, key=lambda el: len(el.get_text(strip=True)))
        text = best.get_text(separator="\n", strip=True)
        if len(text) > 200:
            return text

    body = soup.find("body")
    return body.get_text(separator="\n", strip=True) if body else ""


def scrape_job_url(url: str) -> tuple[str, str | None]:
    """Returns (extracted_text, warning_message_or_None)."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=12, allow_redirects=True)
    except requests.RequestException as e:
        return "", f"Could not fetch the URL: {e}"

    if resp.status_code != 200:
        return "", f"URL returned HTTP {resp.status_code}. Try pasting the job description text instead."

    soup = BeautifulSoup(resp.text, "html.parser")

    is_linkedin = "linkedin.com" in url
    text = _extract_linkedin(soup) if is_linkedin else _extract_generic(soup)

    if not text or len(text.strip()) < 100:
        return "", (
            "Couldn't extract enough text from that URL "
            "(the page may require login or uses JavaScript rendering). "
            "Please paste the job description text manually."
        )

    return text.strip(), None
