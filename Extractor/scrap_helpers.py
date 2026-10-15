from curl_cffi import requests
from bs4 import BeautifulSoup
import os, base64
from urllib.parse import urlparse, urljoin
from Extractor.constants import SOCIAL_DOMAINS, MIN_IMAGE_WIDTH, HEADERS
from django.core.cache import cache

def _parse_domain(url: str) -> str:
    """Extract clean domain. e.g. https://www.github.com/x → github.com"""
    parsed = urlparse(url)
    domain = parsed.netloc
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def _resolve_url(href: str, base_url: str) -> str:
    """Turn any relative URL into absolute."""
    if not href:
        return ""
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return urljoin(base_url, href)


def _get_meta(soup: BeautifulSoup, *attrs) -> str:
    """Try multiple meta tag attribute combinations, return first match."""
    for attr_name, attr_value in attrs:
        tag = soup.find("meta", attrs={attr_name: attr_value})
        if tag and tag.get("content", "").strip():
            return tag["content"].strip()
    return ""


def _domain_to_site_name(domain: str) -> str:
    """
    Extract brand name from domain, handling subdomains correctly.

    Logic: the brand is always the second-to-last part (before TLD).
    - sdjic.org          → parts = [sdjic, org]          → brand = sdjic  → SDJIC
    - github.com         → parts = [github, com]         → brand = github → GitHub
    - blogs.infosys.com  → parts = [blogs, infosys, com] → brand = infosys → Infosys
    - www.bbc.co.uk      → strip www → parts = [bbc, co, uk] → brand = bbc → BBC

    Rule: brand = parts[-2] (second from end, which is always before the TLD)
    Short names (≤5 chars) get uppercased, longer ones get capitalized.
    """
    # Strip www. prefix first
    if domain.startswith("www."):
        domain = domain[4:]

    parts = domain.split(".")

    # Need at least 2 parts (brand + TLD)
    if len(parts) < 2:
        return domain.capitalize()

    # Brand is always second-to-last: github.com → github, blogs.infosys.com → infosys
    brand = parts[-2]

    return brand.upper() if len(brand) <= 5 else brand.capitalize()


def _get_favicons(soup: BeautifulSoup, base_url: str) -> list:
    """
    Collect ALL favicon/icon link tags, sorted best quality first.
    Returns list of dicts: [{"url": "...", "sizes": "192x192", "type": "image/png"}, ...]
    """
    found = []
    seen = set()

    priority = {  # lower = better quality
        "apple-touch-icon": 1,
        "apple-touch-icon-precomposed": 2,
        "icon": 3,
        "shortcut icon": 4,
    }

    for tag in soup.find_all("link", rel=True):
        rel = " ".join(tag.get("rel", [])).lower().strip()
        if rel not in priority:
            continue
        href = tag.get("href", "").strip()
        if not href or href in seen:
            continue
        seen.add(href)
        found.append({
            "url": _resolve_url(href, base_url),
            "sizes": tag.get("sizes", ""),
            "type": tag.get("type", ""),
            "_priority": priority[rel],
        })

    def sort_key(f):
        size_score = 0
        if f["sizes"]:
            try:
                size_score = -int(f["sizes"].lower().split("x")[0])
            except (ValueError, IndexError):
                pass
        return (f["_priority"], size_score)

    found.sort(key=sort_key)

    for f in found:
        del f["_priority"]

    # Always append /favicon.ico as last resort
    default_favicon = _resolve_url("/favicon.ico", base_url)
    if default_favicon not in seen:
        found.append({"url": default_favicon, "sizes": "", "type": "image/x-icon"})

    return found


def _get_social_links(soup: BeautifulSoup) -> dict:
    """
    Scan ALL <a href> tags in the page.
    Returns dict of platform → url.
    e.g. {"facebook": "https://facebook.com/sdjic", "instagram": "..."}
    """
    socials = {}
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if not href.startswith("http"):
            continue
        for domain_keyword, platform_name in SOCIAL_DOMAINS.items():
            if domain_keyword in href and platform_name not in socials:
                socials[platform_name] = href
                break
    return socials


def _get_body_image(soup: BeautifulSoup, base_url: str) -> str:
    """
    Fallback image when og:image is absent.
    Scans <img> tags, skips icons/logos/tiny images.
    Returns first reasonable image URL.
    """
    for img in soup.find_all("img", src=True):
        src = img.get("src", "").strip()
        if not src or src.startswith("data:"):
            continue

        width = img.get("width", "")
        try:
            if width and int(width) < MIN_IMAGE_WIDTH:
                continue
        except ValueError:
            pass

        lower_src = src.lower()
        if any(skip in lower_src for skip in ["icon", "logo", "favicon", "badge", "pixel", "track", "spacer"]):
            continue

        return _resolve_url(src, base_url)
    return ""


def _get_robots_txt(base_url: str) -> str:
    """
    Fetch /robots.txt and return its content (truncated to 500 chars).
    """
    
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    # print(f"""
    #     base_url: {base_url}
    #     parsed: {parsed}
    #     robots_url: {robots_url}
    # """)

    try:
        resp = requests.get(url=robots_url, impersonate="chrome110", timeout=5)
        if not resp.ok:
            return ""
        text = resp.content.decode("utf-8", errors="replace").strip()

        # Sanity check: real robots.txt starts with User-agent or # comment
        if not any(text.startswith(prefix) for prefix in ("User-agent", "user-agent", "#", "Sitemap")):
            return ""
        
        truncate_text = text[:500]
        return truncate_text
    except Exception:
        return ""


def _get_screenshot(url: str) -> str:
    params = {
        "access_key": os.getenv("SCREENSHOT_ONE_ACCESS_KEY"),
        "url": url,
        "format": "jpg",
        "image_quality": 80,
        "response_type": "by_format",
    }

    try: 
        response = requests.get(
            "https://api.screenshotone.com/take",
            params=params,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        return None
    
    base64_encoded = base64.b64encode(response.content).decode("utf-8")
    data_uri = f"data:image/jpeg;base64,{base64_encoded}"
    return data_uri

    return "some screenshot Link here..."
