import time
from bs4 import BeautifulSoup
from Extractor.scrap_helpers import (
    _parse_domain, _domain_to_site_name, _get_body_image, _get_favicons, _get_meta, _get_robots_txt, _get_screenshot,
    _get_social_links
)
from Extractor.constants import TIMEOUT
from curl_cffi import requests

# ─────────────────────────────────────────
#  Layer 1 — requests fetch
# ─────────────────────────────────────────
def _fetch_with_requests(url:str):
    soup = None
    result = {}

    try:
        start = time.time()
        response = requests.get(
            url=url,
            impersonate="chrome110",
            timeout=10
        )
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
#  Extraction
# ─────────────────────────────────────────
def extract_metadata(soup:BeautifulSoup, url:str, result:dict, fields:set) -> dict:
    """ Given a parsed soup + fetch metadata, extract asked fields. """
    result['url'] = url
    result['domain'] = (_parse_domain(url) or "")

    try:
        # ── Tier 1 ─────────────────────────────
        if "title" in fields:
            og_title = _get_meta(soup, ("property", "og:title"), ("name", "og:title"))
            plain_title = soup.title.string.strip() if soup.title and soup.title.string else ""
            result["title"] = og_title or plain_title

        if "description" in fields:
            result["description"] = (
                _get_meta(soup, ("property", "og:description"), ("name", "description"), ("name", "twitter:description"))
                or ""
            )

        if "image" in fields:
            result["image"] = (
                _get_meta(soup, ("property", "og:image"), ("name", "twitter:image"), ("name", "twitter:image:src"))
                or _get_body_image(soup, url)
            )

        if "site_name" in fields:
            result["site_name"] = (
                _get_meta(soup, ("property", "og:site_name"))
                or _domain_to_site_name(result["domain"])
            )

        if "author" in fields:
            result["author"] = (
                _get_meta( soup, ("name", "author"), ("property", "article:author"), ("name", "twitter:creator"))
                or ""
            )

        if "language" in fields:
            html_tag = soup.find("html")
            result["language"] = (
                (html_tag.get("lang", "") if html_tag else "")
                or _get_meta(soup, ("property", "og:locale"), ("name", "language"))
            )

        if "keywords" in fields:
            result["keywords"] = _get_meta(soup, ("name", "keywords"))

        if "theme_color" in fields:
            result["theme_color"] = _get_meta(soup, ("name", "theme-color"))

        if "robots_meta" in fields:
            result["robots_meta"] = _get_meta(soup, ("name", "robots"))

        if "publication_date" in fields:
            result["publication_date"] = _get_meta(soup, ("property", "article:published_time"), ("name", "pubdate"), ("name", "date"))

        if "section" in fields:
            result["section"] = _get_meta(soup, ("property", "article:section"), ("name", "category"))

        if "twitter_handle" in fields:
            result["twitter_handle"] = _get_meta(soup, ("name", "twitter:site"))
        if "twitter_creator" in fields:
            result["twitter_creator"] = _get_meta(soup, ("name", "twitter:creator"))

        if "canonical_url" in fields:
            canonical_tag = soup.find("link", rel="canonical")
            result["canonical_url"] = (
                canonical_tag["href"].strip()
                if canonical_tag and canonical_tag.get("href")
                else url
            )

        if "favicons" in fields:
            result["favicons"] = _get_favicons(soup, url)

        if "social_links" in fields:
            result["social_links"] = _get_social_links(soup)

        # ── Tier 2: second HTTP request ─────────
        if "robots_txt" in fields:
            result["robots_txt"] = _get_robots_txt(url)

        # ── Tier 3: external API ────────────────
        if "screenshot" in fields:
            result["screenshot"] = _get_screenshot(url)
            result["screenshot_note"] = "experimental — may be empty on heavily protected sites"

        result["success"] = True

    except Exception as e:
        result["error"] = f"Extraction error: {str(e)}"

    return result

# ─────────────────────────────────────────
#  Main entry point — called by views.py
# ─────────────────────────────────────────
def extract(url:str, fields:set) -> dict:
    """ Main function. Fetches URL and extracts all metadata. """

    # Scrap the soup data.
    result, soup = _fetch_with_requests(url)
    # print("Fetched Result:--- ", result)

    # If fetch failed entirely (no soup), return what we have
    if soup is None:
        return result
    
    # Extract metadata.
    return extract_metadata(soup, url, result, fields)
    




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
""" 

"""
https://roadmap.sh/full-stack
https://www.github.com/krishj17/
https://www.nytimes.com/international/
https://www.forbes.com/sites/zinnialee/2026/03/30/chinese-american-professor-behind-huawei-backed-power-chip-wafer-maker-becomes-billionaire/

"""

