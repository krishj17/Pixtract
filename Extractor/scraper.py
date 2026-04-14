import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import time
import base64
import re
import mimetypes
import os

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    # Accept-Encoding intentionally omitted — let requests handle it
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

TIMEOUT = 10  # seconds

# Known social platforms — map domain keyword -> platform name
SOCIAL_DOMAINS = {
    "facebook.com": "facebook",
    "fb.com": "facebook",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "instagram.com": "instagram",
    "linkedin.com": "linkedin",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "github.com": "github",
    "pinterest.com": "pinterest",
    "tiktok.com": "tiktok",
    "snapchat.com": "snapchat",
    "telegram.me": "telegram",
    "t.me": "telegram",
    "whatsapp.com": "whatsapp",
    "threads.net": "threads",
}

# Minimum image width to be considered a real image (not an icon/spacer)
MIN_IMAGE_WIDTH = 200


# ─────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────

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

    Note: We do NOT set Accept-Encoding here either — same reason as main request.
    We also decode explicitly with errors='replace' so any encoding issue
    never causes a crash or returns garbled bytes.
    """
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        resp = requests.get(robots_url, headers=HEADERS, timeout=5)
        if not resp.ok:
            return ""
        # Decode explicitly — force UTF-8, replace any undecodable bytes with ?
        # This prevents garbled output even if the server sends wrong encoding
        text = resp.content.decode("utf-8", errors="replace").strip()
        # Sanity check: real robots.txt starts with User-agent or # comment
        if not any(text.startswith(prefix) for prefix in ("User-agent", "user-agent", "#", "Sitemap")):
            return ""
        return text[:500]
    except Exception:
        return ""


def _take_screenshot(url: str) -> str:
    """
    Launch headless Chromium, remove common popups/overlays,
    take a viewport screenshot, return as base64 string.
    Returns empty string if anything fails.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return ""   # Playwright not installed yet

    # JS to remove popup/overlay elements before screenshotting.
    # Looks for fixed/sticky elements with high z-index, or common class names.
    REMOVE_OVERLAYS_JS = """
        () => {
            const overlaySelectors = [
                '[class*="cookie"]', '[class*="consent"]', '[class*="gdpr"]',
                '[class*="newsletter"]', '[id*="cookie"]', '[id*="consent"]',
            ];
            overlaySelectors.forEach(sel => {
                document.querySelectorAll(sel).forEach(el => el.remove());
            });

            // Only remove fixed elements that cover >30% of viewport — actual overlays
            const vw = window.innerWidth;
            const vh = window.innerHeight;
            document.querySelectorAll('*').forEach(el => {
                const style = window.getComputedStyle(el);
                const zIndex = parseInt(style.zIndex) || 0;
                if (style.position === 'fixed' && zIndex > 100) {
                    const rect = el.getBoundingClientRect();
                    const coverage = (rect.width * rect.height) / (vw * vh);
                    if (coverage > 0.30) el.remove();  // only if covers 30%+ of screen
                }
            });
        }
    """

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(url, timeout=15000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)       # wait for popups to appear
            page.evaluate(REMOVE_OVERLAYS_JS) # then remove them
            page.wait_for_timeout(500)        # let removals settle visually
            
            screenshot_bytes = page.screenshot(
                type="jpeg",
                quality=70,          # 70% quality keeps size reasonable
                full_page=False,     # viewport only — full_page=True can be 10MB+
            )
            browser.close()

        return "data:image/jpeg;base64," + base64.b64encode(screenshot_bytes).decode("utf-8")

    except Exception as e:
        print("ERROR IN SCREENSHOT SECTION: ",e)
        return ""


# ─────────────────────────────────────────
#  Layer 1 — requests fetch
# ─────────────────────────────────────────
def _fetch_with_requests(url: str):
    """
    Fetch the URL. Returns (fetch_result_dict, soup_or_None).
    Separated from extraction so Playwright can reuse the same extraction logic.
    """
    result = {
        "success": False,
        "blocked": False,
        "error": None,
        "http_status": None,
        "duration_ms": None,
        "fetch_method": "requests",
        "content_type": "",
        "_include_screenshot": False
    }
    soup = None

    try:
        start = time.time()
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        duration_ms = round((time.time() - start) * 1000)

        result["http_status"] = response.status_code
        result["duration_ms"] = duration_ms
        result["content_type"] = response.headers.get("Content-Type", "").split(";")[0].strip()

        if response.status_code in (403, 429):
            result["blocked"] = True
            result["error"] = f"Site blocked the request (HTTP {response.status_code})"
            return result, soup

        if not response.ok:
            result["error"] = f"HTTP {response.status_code}"
            return result, soup

        # Explicitly decode with UTF-8, replacing bad bytes rather than crashing.
        # response.text uses response.encoding which is sometimes wrong (e.g. ISO-8859-1
        # declared but actual content is UTF-8). Using response.content + manual decode
        # is more reliable across sites.
        html = response.content.decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")

    except requests.exceptions.ConnectionError:
        result["error"] = "Could not connect to the site"
    except requests.exceptions.Timeout:
        result["error"] = f"Request timed out after {TIMEOUT}s"
    except requests.exceptions.TooManyRedirects:
        result["error"] = "Too many redirects"
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"

    return result, soup


# ─────────────────────────────────────────
#  Extraction — shared between Layer 1 and Layer 2
# ─────────────────────────────────────────
def extract_metadata(soup: BeautifulSoup, url: str, fetch_result: dict) -> dict:
    """
    Given a parsed soup + fetch metadata, extract all fields.
    This function is intentionally decoupled from how the HTML was fetched,
    so Playwright can call it with the same interface later.
    """
    result = {
        **fetch_result,
        "url": url,
        "canonical_url": "",
        "domain": _parse_domain(url),
        "title": "",
        "description": "",
        "keywords": "",
        "image": "",
        "screenshot": "",
        "screenshot_note": "",
        "favicons": [],
        "site_name": "",
        "author": "",
        "language": "",
        "theme_color": "",
        "robots_meta": "",
        "robots_txt": "",
        "publication_date": "",
        "twitter_handle": "",
        "twitter_creator": "",
        "section": "",
        "social_links": {},
    }

    try:
        # Title
        og_title = _get_meta(soup, ("property", "og:title"), ("name", "og:title"))
        plain_title = soup.title.string.strip() if soup.title and soup.title.string else ""
        result["title"] = og_title or plain_title

        # Description
        result["description"] = _get_meta(
            soup,
            ("property", "og:description"),
            ("name", "description"),
            ("name", "twitter:description"),
        )

        # Image — OG/Twitter first, body scan fallback
        result["image"] = (
            _get_meta(soup, ("property", "og:image"), ("name", "twitter:image"), ("name", "twitter:image:src"))
            or _get_body_image(soup, url)
        )

        # Site name — OG tag, then smart domain-derived fallback
        result["site_name"] = (
            _get_meta(soup, ("property", "og:site_name"))
            or _domain_to_site_name(result["domain"])
        )

        # Author
        result["author"] = _get_meta(
            soup,
            ("name", "author"),
            ("property", "article:author"),
            ("name", "twitter:creator"),
        )

        # Language
        html_tag = soup.find("html")
        result["language"] = (
            (html_tag.get("lang", "") if html_tag else "")
            or _get_meta(soup, ("property", "og:locale"), ("name", "language"))
        )

        # Keywords
        result["keywords"] = _get_meta(soup, ("name", "keywords"))

        # Theme color
        result["theme_color"] = _get_meta(soup, ("name", "theme-color"))

        # Robots meta tag (e.g. "noindex, nofollow" or "max-image-preview:large")
        result["robots_meta"] = _get_meta(soup, ("name", "robots"))

        # Publication date
        result["publication_date"] = _get_meta(
            soup,
            ("property", "article:published_time"),
            ("name", "pubdate"),
            ("name", "date"),
        )

        # Section / category
        result["section"] = _get_meta(
            soup,
            ("property", "article:section"),
            ("name", "category"),
        )

        # Twitter handles
        result["twitter_handle"] = _get_meta(soup, ("name", "twitter:site"))
        result["twitter_creator"] = _get_meta(soup, ("name", "twitter:creator"))

        # Canonical URL
        canonical_tag = soup.find("link", rel="canonical")
        result["canonical_url"] = (
            canonical_tag["href"].strip()
            if canonical_tag and canonical_tag.get("href")
            else url
        )

        # Favicons — all, best quality first
        result["favicons"] = _get_favicons(soup, url)

        # Social links — scanned from all <a> tags
        result["social_links"] = _get_social_links(soup)

        # robots.txt
        result["robots_txt"] = _get_robots_txt(url)

        # Screenshot — only taken if requested (slow, ~3-5 seconds)
        if fetch_result.get("_include_screenshot"):
            result["screenshot"] = _take_screenshot(url)
            result["screenshot_note"] = "experimental — may be empty on heavily protected sites"

        result["success"] = True

    except Exception as e:
        result["error"] = f"Extraction error: {str(e)}"

    return result


# ─────────────────────────────────────────
#  Layer 2 — Playwright (stub)
# ─────────────────────────────────────────
def _fetch_with_playwright(url: str):
    """
    Fallback for JS-heavy sites.
    Requires: pip install playwright && playwright install chromium
    TODO: implement after Layer 1 is deployed and tested.

    When implemented, this should return (fetch_result_dict, soup)
    with the same shape as _fetch_with_requests — so extract_metadata()
    can be called identically.
    """
    raise NotImplementedError("Playwright layer not yet implemented")


# ─────────────────────────────────────────
#  Main entry point — called by views.py
# ─────────────────────────────────────────
def extract(url: str, use_playwright_fallback: bool = False, screenshot: bool = False) -> dict:
    """
    Main function. Fetches URL and extracts all metadata.

    Args:
        url: The URL to extract from.
        use_playwright_fallback: Enable for paid-tier requests (future).
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Fetch html page with requests FIRST.
    fetch_result, soup = _fetch_with_requests(url)

    # If fetch failed entirely (no soup), return what we have
    if soup is None:
        return fetch_result
    
    # Wether to include screenshort or not.
    if screenshot:
        fetch_result['_include_screenshot'] = True
    
    # Extract metadata.
    extracted = extract_metadata(soup, url, fetch_result)

    # If blocked and fallback enabled, retry with Playwright
    if extracted["blocked"] and use_playwright_fallback:
        try:
            fetch_result, soup = _fetch_with_playwright(url)
            if soup:
                extracted = extract_metadata(soup, url, fetch_result)
        except NotImplementedError:
            pass

    return extracted


# ─────────────────────────────────────────
#  Quick test: python scraper.py
# ─────────────────────────────────────────
"""
if __name__ == "__main__":
    import json
    # test_urls = [
    #     "https://revsportz.in/ipl-2026-josh-hazlewood-links-up-with-rcb-in-bengaluru/",
    #     "https://blogs.infosys.com/emerging-technology-solutions/iedps/addressing-qa-gaps-in-agentic-ai.html",
    # ]
    # for url in test_urls:
    #     print(f"\n{'='*60}")
    #     print(f"Testing: {url}")
    #     print('='*60)
    #     data = extract(url)
    #     print(json.dumps(data, indent=2))

    url = ""
    print(f"\n{'='*60}")
    print(f"Testing: {url}")
    print('='*60)
    data = extract(url, False, True)
    print(json.dumps(data, indent=2))

    if data.get("screenshot"):
        base64_url_string = data['screenshot']
        header, encoded_data = base64_url_string.split(';base64,')
        mime_type = header.split(':')[1]
        extension = mimetypes.guess_extension(mime_type) or '.png' # Default to .png if unknown
        image_data = base64.b64decode(encoded_data)
        output_filename = "_"+data['site_name']+"_" + extension # Example filename
        with open(output_filename, "wb") as image_file:
            image_file.write(image_data)

        print(f"Image successfully saved as {output_filename}")
""" 



"""
https://roadmap.sh/full-stack
https://www.github.com/krishj17/
https://www.nytimes.com/international/
https://www.forbes.com/sites/zinnialee/2026/03/30/chinese-american-professor-behind-huawei-backed-power-chip-wafer-maker-becomes-billionaire/


"""