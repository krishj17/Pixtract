
# Headers for requests.
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
# Timeout for requests fetch.
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

ALL_FIELDS = {
    "title", "description", "image", "site_name", "author", "language", "keywords", "theme_color", "robots_meta", "publication_date",
    "section", "twitter_handle", "twitter_creator", "canonical_url", "favicons", "social_links", "robots_txt", "screenshot"
}

SIGNED_ONLY_KEYS = {'keywords','image','screenshot','screenshot_note','theme_color','robots_meta','robots_txt','social_links'}

