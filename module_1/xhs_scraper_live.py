#!/usr/bin/env python3
"""
XHS Live Scraper — Module 1
============================
Scrapes Xiaohongshu (XHS / RedNote) search results using DrissionPage
(a real Chrome browser session). Extracts raw post data including:
  - titles, captions, hashtags  (stored 100% unchanged)
  - likes, saves, comment counts
  - cover image URLs
  - detail-page image gallery URLs
  - video thumbnail URLs (for video posts)

Then:
  - Saves a completely raw archive to data/xhs_raw_posts.json
  - Anonymizes creator names (one-way SHA-256 hash)
  - AI-captions the first image of each post using OpenRouter vision
  - Saves the enriched, anonymized data to data/xhs_posts.json
    (this is what xhs_trend_builder.py reads)

PREREQUISITES
  1. Chrome browser installed
  2. Dependencies:  pip3 install DrissionPage pandas tqdm openpyxl
     OR use the venv:  source .venv/bin/activate
  3. Root .env has OPENROUTER_API_KEY and DEFAULT_MODEL
  4. First run: XHS QR code will appear — scan with your phone app

USAGE
  # with venv (recommended on Mac):
  .venv/bin/python3 xhs_scraper_live.py --keywords "Louis Vuitton" "LV" "路易威登" --times 3

  # with system python3 (if packages already installed globally):
  python3 xhs_scraper_live.py --keywords "LV" "路易威登" --times 2 --no-caption

  # After scraping, restrict to March–April (or any window in run_config.json):
  #   cd module_1 && ../.venv/bin/python3 filter_posts_by_config.py
  # See WEEK11_DATE_FILTER.md

  # Fast ~200 posts (detail + trends, skip slow vision API):
  #   ../.venv/bin/python3 xhs_scraper_live.py -k "LV" "路易威登" "LV包包" --times 5 \
  #     --max-posts 200 --fast --no-caption
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────────────────────────
# Load .env from module_1 or parent directory
# ─────────────────────────────────────────────────────────────────
def _load_env():
    for env_path in [Path(__file__).parent / ".env", Path(__file__).parent.parent / ".env"]:
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

_load_env()

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
VISION_MODEL       = os.environ.get("DEFAULT_MODEL", "openai/gpt-4o-mini")

DATA_DIR              = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
RAW_OUTPUT_PATH       = DATA_DIR / "xhs_raw_posts.json"
PROCESSED_OUTPUT_PATH = DATA_DIR / "xhs_posts.json"

XHS_LOGIN_URL  = "https://www.xiaohongshu.com/explore"
XHS_SEARCH_URL = "https://www.xiaohongshu.com/search_result?keyword={keyword}"


# ─────────────────────────────────────────────────────────────────
# Anonymization
# ─────────────────────────────────────────────────────────────────
def anonymize_creator(username: str) -> str:
    """Consistent one-way hash — same user always maps to the same anon ID."""
    h = hashlib.sha256(username.encode("utf-8")).hexdigest()[:8]
    return f"user_{h}"


# ─────────────────────────────────────────────────────────────────
# AI image captioning via OpenRouter
# ─────────────────────────────────────────────────────────────────
def _fetch_image_b64(url: str) -> str | None:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.xiaohongshu.com/",
            }
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            return base64.b64encode(r.read()).decode()
    except Exception as e:
        print(f"    [WARN] Image download failed: {e}")
        return None


def caption_image(image_url: str, title: str = "") -> str:
    """Ask the vision model to describe an XHS post image."""
    if not OPENROUTER_API_KEY:
        return "[skipped: no API key]"

    b64 = _fetch_image_b64(image_url)
    if not b64:
        return "[skipped: image download failed]"

    ext  = image_url.split("?")[0].rsplit(".", 1)[-1].lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "webp": "image/webp", "gif": "image/gif"}.get(ext, "image/jpeg")

    payload = json.dumps({
        "model": VISION_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "You are analyzing a Xiaohongshu post image for trend research.\n"
                        f"Post title: \"{title}\"\n\n"
                        "In 2-3 sentences describe: products shown, visual aesthetic, "
                        "colors, styling, any visible text or branding. Be specific, factual."
                    )
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"}
                }
            ]
        }],
        "max_tokens": 300,
    }).encode()

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/m-ny/mvp",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[AI caption failed: {e}]"


# ─────────────────────────────────────────────────────────────────
# Parsing helpers
# ─────────────────────────────────────────────────────────────────
def _parse_count(raw) -> int:
    """Convert XHS display numbers ('1.2万', '3k', '452') to int."""
    s = str(raw or "0").strip().replace(",", "")
    try:
        if "万" in s:
            return int(float(s.replace("万", "")) * 10_000)
        if "k" in s.lower():
            return int(float(s.lower().replace("k", "")) * 1_000)
        return int(float(s))
    except ValueError:
        return 0


def _fill_defaults(post: dict) -> dict:
    """Set missing detail fields to safe defaults."""
    post.setdefault("date", "")
    post.setdefault("saves", 0)
    post.setdefault("comments", 0)
    post.setdefault("caption", "")
    post.setdefault("hashtags", [])
    post.setdefault("all_image_urls",
                    [post["cover_url"]] if post.get("cover_url") else [])
    post.setdefault("is_video", False)
    post.setdefault("video_url", "")
    post.setdefault("raw_comments", [])   # comment scraping result
    return post


def _parse_hashtags(raw: str) -> list[str]:
    tags = re.findall(r"#[\w\u4e00-\u9fff·]+", raw or "")
    return tags


def _extract_detail_date(detail_tab) -> str:
    """Best-effort note publish/edit date from detail DOM (XHS changes class names)."""
    selectors = (
        ".date",
        ".date-note",
        ".bottom-container .date",
        "span.time",
        ".publish-date",
        ".note-top .date",
        "tag:time",
    )
    for sel in selectors:
        try:
            el = detail_tab.ele(sel, timeout=2)
            if el and getattr(el, "text", None):
                t = str(el.text).strip()
                if t and t not in ("", "-"):
                    return t
        except Exception:
            continue
    return ""


# ─────────────────────────────────────────────────────────────────
# Core scraper using DrissionPage directly
# ─────────────────────────────────────────────────────────────────
class XHSLiveScraper:
    """
    Drives a real Chrome session on XHS.
    Extracts post cards + detail-page images/videos.
    """

    def __init__(self, fast: bool = False, skip_comments: bool = False):
        try:
            from DrissionPage import ChromiumPage, ChromiumOptions
        except ImportError:
            print(
                "ERROR: DrissionPage not installed.\n"
                "Run:  .venv/bin/pip install DrissionPage pandas tqdm openpyxl\n"
                "Then: .venv/bin/python3 xhs_scraper_live.py ..."
            )
            sys.exit(1)

        # Avoid fixed-port CDP attach failures (default 127.0.0.1:9222) by letting
        # DrissionPage pick an available debugging port + isolated user-data-dir.
        opts = ChromiumOptions()
        opts.auto_port()
        self.browser  = ChromiumPage(addr_or_opts=opts)  # the browser / main tab
        self.main_tab = self.browser                     # alias — used for search page
        self.fast = fast
        self.skip_comments = skip_comments

    # ── Login ──────────────────────────────────────────────────────
    def ensure_login(self):
        self._get_safe(self.main_tab, XHS_LOGIN_URL)
        time.sleep(3)
        if self.main_tab.ele(".login-container", timeout=3):
            print("\n[LOGIN] QR code shown — scan with XHS app on your phone.")
            print("[LOGIN] Waiting up to 5 minutes…")
            for _ in range(300):
                time.sleep(1)
                if not self.main_tab.ele(".login-container", timeout=1):
                    print("[LOGIN] Logged in successfully.")
                    return
            print("[WARN] Login timeout — continuing anyway (may fail).")
        else:
            print("[LOGIN] Already logged in.")

    # ── Safe navigation with reconnect ─────────────────────────────
    def _get_safe(self, tab, url: str, retries: int = 2):
        """Navigate `tab` to `url`, reconnecting if the tab is dead."""
        from DrissionPage.errors import PageDisconnectedError
        for attempt in range(retries + 1):
            try:
                tab.get(url)
                return
            except Exception as e:
                if attempt < retries:
                    print(f"    [RETRY {attempt+1}] Connection issue, waiting 4 s… ({e.__class__.__name__})")
                    time.sleep(4)
                    # Try to reconnect main tab via the browser object
                    try:
                        self.main_tab = self.browser.get_tab()
                    except Exception:
                        pass
                else:
                    raise

    def _recover_search_tab(self, url: str) -> None:
        """Re-open search URL after PageDisconnectedError (long scroll sessions)."""
        try:
            self.main_tab = self.browser.get_tab()
        except Exception:
            pass
        self._get_safe(self.main_tab, url, retries=3)
        time.sleep(3.0 if not self.fast else 1.5)

    # ── Search ─────────────────────────────────────────────────────
    def search(
        self,
        keyword: str,
        scroll_times: int = 3,
        filter_words: list[str] | None = None,
        max_cards: int | None = None,
    ) -> list[dict]:
        """
        Search XHS for `keyword`, scroll `scroll_times` pages, return card dicts.
        Optional `filter_words`: only keep posts whose title contains at least
        one of these words (case-insensitive). Use for luxury/fashion filtering.
        `max_cards`: stop collecting once this many unique cards (faster path to N posts).
        """
        from urllib.parse import quote

        try:
            from DrissionPage.errors import PageDisconnectedError
        except Exception:  # pragma: no cover
            PageDisconnectedError = Exception  # type: ignore

        encoded = quote(keyword)
        # note_type=0 → all notes; type=51 → image posts only (better for fashion)
        url = XHS_SEARCH_URL.format(keyword=encoded) + "&type=51"
        print(f"  [SEARCH] {url}")
        self._get_safe(self.main_tab, url)
        time.sleep(4.0 if not self.fast else 2.5)  # give XHS time to fully render

        cards: list[dict] = []
        seen_links: set[str] = set()

        scroll_n = 0
        disconnect_streak = 0
        while scroll_n < scroll_times:
            print(f"  [SCROLL] {scroll_n + 1}/{scroll_times}")
            try:
                new_cards = self._extract_cards(keyword)
                for c in new_cards:
                    if not c["post_link"] or c["post_link"] in seen_links:
                        continue
                    if filter_words:
                        title_lower = (c.get("title") or "").lower()
                        if not any(w.lower() in title_lower for w in filter_words):
                            continue
                    seen_links.add(c["post_link"])
                    cards.append(c)
                    if max_cards is not None and len(cards) >= max_cards:
                        print(f"  [CAP] Reached max_cards={max_cards} for this keyword")
                        print(f"  [FOUND] {len(cards)} cards for '{keyword}'")
                        return cards
                self.main_tab.scroll.to_bottom()
                time.sleep(2.5 if not self.fast else 1.0)
            except PageDisconnectedError:
                disconnect_streak += 1
                if disconnect_streak > 6:
                    print(
                        "    [Abort] Too many disconnects on this keyword — "
                        f"returning {len(cards)} cards collected so far."
                    )
                    print(f"  [FOUND] {len(cards)} cards for '{keyword}'")
                    return cards
                print(
                    f"    [RECOVER] Page disconnected at scroll {scroll_n + 1} — "
                    "reloading search and continuing…"
                )
                self._recover_search_tab(url)
                continue
            disconnect_streak = 0
            scroll_n += 1

        print(f"  [FOUND] {len(cards)} cards for '{keyword}'")
        return cards

    def _extract_cards(self, keyword: str) -> list[dict]:
        """Parse all visible post cards on the current search page."""
        results = []
        # XHS uses several possible selectors depending on layout
        sections = (self.main_tab.eles(".note-item")
                    or self.main_tab.eles(".feed-item")
                    or self.main_tab.eles(".search-item"))
        for sec in sections:
            try:
                # Post link — try the cover anchor first, then any <a>
                link_el = (sec.ele(".cover", timeout=1)
                           or sec.ele("tag:a", timeout=1))
                post_link = (link_el.link if link_el else "") or ""
                if not post_link:
                    continue

                # Cover thumbnail
                cover_img = sec.ele("tag:img", timeout=1)
                cover_url = (cover_img.attr("src") or cover_img.attr("data-src")
                             if cover_img else "") or ""

                # Footer info
                footer  = sec.ele(".footer", timeout=1)
                title   = ""
                creator = ""
                likes   = "0"
                if footer:
                    t = footer.ele(".title", timeout=1)
                    title = t.text if t else ""
                    n = footer.ele(".name", timeout=1)
                    creator = n.text if n else ""
                    lw = footer.ele(".like-wrapper", timeout=1)
                    likes = lw.text if lw else "0"

                results.append({
                    "keyword":     keyword,
                    "post_link":   post_link,
                    "title":       title,
                    "raw_creator": creator,
                    "likes":       _parse_count(likes),
                    "cover_url":   cover_url,
                })
            except Exception as e:
                print(f"    [WARN] Card parse error: {e}")
        return results

    # ── Detail page (NEW TAB — keeps search tab alive) ──────────────
    def fetch_detail(self, post: dict) -> dict:
        """
        Open the post detail page in a NEW TAB, extract data, close the tab.
        This keeps the search tab alive and prevents PageDisconnectedError.
        """
        link = post.get("post_link", "")
        if not link:
            return _fill_defaults(post)

        detail_tab = None
        try:
            detail_tab = self.browser.new_tab(link)
            time.sleep(3.0 if not self.fast else 1.8)

            # ── stats ──
            post["date"] = _extract_detail_date(detail_tab)

            saves_el = detail_tab.ele(".collect-wrapper .count", timeout=3)
            post["saves"] = _parse_count(saves_el.text if saves_el else "0")

            comments_el = detail_tab.ele(".chat-wrapper .count", timeout=3)
            post["comments"] = _parse_count(comments_el.text if comments_el else "0")

            # ── caption + hashtags ──
            desc_el = detail_tab.ele("tag:div@class=desc", timeout=3)
            raw_desc = ""
            if desc_el:
                span = desc_el.ele("tag:span", timeout=1)
                raw_desc = (span.text if span else desc_el.text).replace("\n", " ")
            post["caption"] = raw_desc

            hashtag_els = detail_tab.eles("#hash-tag")
            post["hashtags"] = ([el.text for el in hashtag_els]
                                if hashtag_els else _parse_hashtags(raw_desc))

            # ── images ──
            image_urls: list[str] = []
            # Try the note image container first
            note_swiper = detail_tab.ele(".note-image", timeout=2)
            if note_swiper:
                for img in note_swiper.eles("tag:img"):
                    src = img.attr("src") or img.attr("data-src") or ""
                    if src and src not in image_urls and "avatar" not in src:
                        image_urls.append(src)
            # Fallback: all imgs in note body
            if not image_urls:
                note_body = (detail_tab.ele(".note-container", timeout=2)
                             or detail_tab.ele(".note-detail", timeout=2))
                if note_body:
                    for img in note_body.eles("tag:img"):
                        src = img.attr("src") or img.attr("data-src") or ""
                        if src and src not in image_urls and "avatar" not in src:
                            image_urls.append(src)
            if not image_urls and post.get("cover_url"):
                image_urls = [post["cover_url"]]
            post["all_image_urls"] = image_urls

            # ── video ──
            video_el = detail_tab.ele("tag:video", timeout=2)
            post["is_video"] = bool(video_el)
            if video_el:
                post["video_url"] = video_el.attr("src") or ""
                poster = video_el.attr("poster") or ""
                if poster and not image_urls:
                    post["all_image_urls"] = [poster]
            else:
                post["video_url"] = ""

            # ── comments + replies ──
            if self.skip_comments:
                post["raw_comments"] = []
            else:
                post["raw_comments"] = self._scrape_comments(
                    detail_tab, max_scrolls=3 if not self.fast else 1
                )

        except Exception as e:
            print(f"    [WARN] Detail fetch failed for {link}: {e.__class__.__name__}")
            post = _fill_defaults(post)
        finally:
            if detail_tab:
                try:
                    detail_tab.close()
                except Exception:
                    pass

        return post

    # ── Comment scraping ───────────────────────────────────────────
    def _scrape_comments(self, tab, max_scrolls: int = 3) -> list[dict]:
        """
        Scrape all visible comments (and their replies) from the current
        post detail tab.

        Returns a list of comment dicts:
          {
            "commenter_id": "user_<hash>",   ← anonymized, never the real name
            "text": "raw comment text",       ← unchanged
            "likes": 12,
            "replies": [
              {"commenter_id": "user_<hash>", "text": "raw reply text", "likes": 0},
              ...
            ]
          }

        Commenter names are NEVER stored anywhere — only the hash is kept.
        """
        comments: list[dict] = []

        # Scroll the comment section a few times to load more comments
        try:
            comment_section = (
                tab.ele(".comments-container",  timeout=3)
                or tab.ele(".comment-list",      timeout=2)
                or tab.ele(".note-comment",      timeout=2)
            )
            if comment_section:
                for _ in range(max_scrolls):
                    tab.scroll.to_bottom()
                    time.sleep(1.2)
        except Exception:
            pass

        # ── try multiple CSS selector patterns (XHS changes these) ──
        # Pattern 1: comment-item inside comments-container
        # Pattern 2: .list-container > div items
        comment_items = (
            tab.eles(".comment-item")
            or tab.eles(".commentItem")
            or tab.eles(".note-comment .list-container .item")
            or []
        )

        for item in comment_items:
            try:
                # Comment text — XHS uses several class names
                text_el = (
                    item.ele(".note-text",        timeout=1)
                    or item.ele(".content",        timeout=1)
                    or item.ele(".comment-content",timeout=1)
                    or item.ele("tag:span",        timeout=1)
                )
                raw_text = text_el.text.strip() if text_el else ""
                if not raw_text:
                    continue

                # Commenter name — extract only to hash it, never store plain
                name_el = (
                    item.ele(".user-info .name",  timeout=1)
                    or item.ele(".author",         timeout=1)
                    or item.ele(".user-nick",      timeout=1)
                    or item.ele(".nickname",       timeout=1)
                )
                raw_name = name_el.text.strip() if name_el else f"anon_{id(item)}"
                commenter_id = anonymize_creator(raw_name)

                # Comment likes
                like_el = (
                    item.ele(".like-wrapper .count", timeout=1)
                    or item.ele(".like-count",        timeout=1)
                    or item.ele(".count",             timeout=1)
                )
                comment_likes = _parse_count(like_el.text if like_el else "0")

                # ── replies ──
                replies: list[dict] = []
                reply_items = (
                    item.eles(".reply-item")
                    or item.eles(".replyItem")
                    or item.eles(".sub-comment-item")
                    or []
                )
                for reply in reply_items:
                    try:
                        r_text_el = (
                            reply.ele(".note-text",         timeout=1)
                            or reply.ele(".content",         timeout=1)
                            or reply.ele(".comment-content", timeout=1)
                            or reply.ele("tag:span",         timeout=1)
                        )
                        r_text = r_text_el.text.strip() if r_text_el else ""
                        if not r_text:
                            continue

                        r_name_el = (
                            reply.ele(".user-info .name", timeout=1)
                            or reply.ele(".author",        timeout=1)
                            or reply.ele(".user-nick",     timeout=1)
                        )
                        r_raw_name = r_name_el.text.strip() if r_name_el else f"anon_{id(reply)}"
                        r_commenter_id = anonymize_creator(r_raw_name)

                        r_like_el = reply.ele(".like-wrapper .count", timeout=1) \
                                    or reply.ele(".count", timeout=1)
                        r_likes = _parse_count(r_like_el.text if r_like_el else "0")

                        replies.append({
                            "commenter_id": r_commenter_id,
                            "text":         r_text,   # raw, unchanged
                            "likes":        r_likes,
                        })
                    except Exception:
                        continue

                comments.append({
                    "commenter_id": commenter_id,
                    "text":         raw_text,   # raw, unchanged
                    "likes":        comment_likes,
                    "replies":      replies,
                })

            except Exception:
                continue

        return comments

    def close(self):
        try:
            self.browser.quit()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────
# Build output records
# ─────────────────────────────────────────────────────────────────
def max_live_numeric_id(processed: list[dict]) -> int:
    """Highest N in post_id 'live_N' / 'live_NNNN' (0 if none)."""
    best = 0
    for p in processed:
        pid = str(p.get("post_id", "")).strip()
        if pid.startswith("live_"):
            try:
                best = max(best, int(pid[5:]))
            except ValueError:
                continue
    return best


def build_records(
    raw_posts: list[dict],
    category: str,
    do_caption: bool,
    start_index: int = 1,
) -> tuple[list[dict], list[dict]]:
    """
    Returns (raw_records, processed_records).

    raw_records      — 100 % unchanged scraped data (xhs_raw_posts.json)
    processed_records — anonymized + AI-enriched (xhs_posts.json → trend builder)
    `start_index` — first live_XXXX number (use when appending to an existing file).
    """
    raw_records: list[dict] = []
    processed: list[dict] = []

    for offset, post in enumerate(raw_posts):
        idx = start_index + offset
        pid = f"live_{idx:04d}"

        # ── RAW record (nothing changed) ──
        raw_records.append({"post_id": pid, "scraped_at": datetime.utcnow().isoformat() + "Z", **post})

        # ── PROCESSED record ──
        # Creator anonymized, content untouched
        creator_anon = anonymize_creator(post.get("raw_creator") or f"unknown_{idx}")

        # Pick the first real image for captioning
        all_imgs   = post.get("all_image_urls", [])
        first_img  = next((u for u in all_imgs if u), post.get("cover_url", ""))
        ai_caption = ""
        if do_caption and first_img:
            print(f"  [AI] Captioning image for post {pid}…")
            ai_caption = caption_image(first_img, post.get("title", ""))
            time.sleep(0.4)

        # Comments: text + replies are raw/unchanged; commenter names already hashed
        # raw_comments contains {"commenter_id", "text", "likes", "replies":[...]}
        comments_data = post.get("raw_comments", [])

        processed.append({
            "post_id":        pid,
            "keyword":        post.get("keyword", ""),
            "category":       category,
            "date":           post.get("date", ""),
            "title":          post.get("title", ""),        # raw — UNCHANGED
            "caption":        post.get("caption", ""),      # raw — UNCHANGED
            "hashtags":       post.get("hashtags", []),     # raw — UNCHANGED
            "likes":          post.get("likes", 0),
            "comment_count":  post.get("comments", 0),     # total count shown on post
            "saves":          post.get("saves", 0),
            "creator":        creator_anon,                 # anonymized
            "post_link":      post.get("post_link", ""),
            "all_image_urls": all_imgs,
            "cover_url":      post.get("cover_url", ""),
            "is_video":       post.get("is_video", False),
            "video_url":      post.get("video_url", ""),
            "image_caption":  ai_caption,
            # ── comments (text raw, commenter IDs anonymized) ──
            "comments_scraped": comments_data,              # full list with replies
            "comments_count_scraped": len(comments_data),  # how many we actually got
        })

    return raw_records, processed


# ─────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Scrape live XHS posts and feed them into the Module 1 trend builder."
    )
    parser.add_argument("--keywords", "-k", nargs="+", required=True,
                        help='XHS search keywords, e.g. --keywords "LV" "高奢穿搭" "Dior彩妆"')
    parser.add_argument("--times",    "-t", type=int, default=3,
                        help="Scroll-pages per keyword (more = more posts, default 3)")
    parser.add_argument("--category", "-c", default="luxury_fashion",
                        help='Category label written into xhs_posts.json (default: luxury_fashion)')
    parser.add_argument("--filter", "-f", nargs="*", dest="filter_words",
                        help="Only keep posts whose TITLE contains at least one of these words. "
                             "Useful to filter out off-topic results. "
                             'e.g. --filter "LV" "Dior" "包" "穿搭" "奢"')
    parser.add_argument("--no-detail", action="store_true",
                        help="Skip detail-page visits (faster, but no caption/hashtag/date/images)")
    parser.add_argument("--no-caption", action="store_true",
                        help="Skip AI image captioning")
    parser.add_argument(
        "--max-posts",
        type=int,
        default=None,
        metavar="N",
        help="Stop after N total posts (caps scroll + detail work). Use with --times 5–8 to reach ~200.",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Shorter sleeps on search/detail (still real browser; much faster than default).",
    )
    parser.add_argument(
        "--skip-comments",
        action="store_true",
        help="Do not scrape comment threads (saves a lot of time per post).",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Merge into existing data/xhs_posts.json + xhs_raw_posts.json (dedupe by post_link, new IDs).",
    )
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(line_buffering=True)  # noqa: SLF001
    except Exception:
        pass

    print("=" * 60)
    print("XHS Live Scraper — Module 1")
    print(f"Keywords  : {args.keywords}")
    print(f"Scroll×   : {args.times} per keyword")
    print(f"Category  : {args.category}")
    print(f"Filter    : {args.filter_words or 'none (all results kept)'}")
    print(f"Detail    : {not args.no_detail}")
    print(f"AI caption: {not args.no_caption}")
    print(f"Max posts : {args.max_posts or 'no cap'}")
    print(f"Fast mode : {args.fast}")
    print(f"Comments  : {not args.skip_comments}")
    print(f"Append    : {args.append}")
    print("=" * 60)

    existing_processed: list[dict] = []
    existing_raw: list[dict] = []
    existing_links: set[str] = set()
    if args.append:
        if PROCESSED_OUTPUT_PATH.exists():
            try:
                existing_processed = json.loads(
                    PROCESSED_OUTPUT_PATH.read_text(encoding="utf-8")
                )
                if not isinstance(existing_processed, list):
                    existing_processed = []
            except Exception as e:
                print(f"[WARN] Could not read existing {PROCESSED_OUTPUT_PATH}: {e}")
                existing_processed = []
        if RAW_OUTPUT_PATH.exists():
            try:
                existing_raw = json.loads(RAW_OUTPUT_PATH.read_text(encoding="utf-8"))
                if not isinstance(existing_raw, list):
                    existing_raw = []
            except Exception as e:
                print(f"[WARN] Could not read existing {RAW_OUTPUT_PATH}: {e}")
                existing_raw = []
        existing_links = {
            str(p.get("post_link", "") or "").strip()
            for p in existing_processed
            if p.get("post_link")
        }
        print(f"[APPEND] Existing posts: {len(existing_processed)} (dedupe by post_link)")

    scraper = XHSLiveScraper(fast=args.fast, skip_comments=args.skip_comments)
    scraper.ensure_login()

    all_raw: list[dict] = []
    remaining: int | None = args.max_posts

    for kw in args.keywords:
        if remaining is not None and remaining <= 0:
            break
        print(f"\n[KEYWORD] {kw}")
        need_this_keyword = remaining if remaining is not None else None
        cards = scraper.search(
            kw,
            scroll_times=args.times,
            filter_words=args.filter_words or None,
            max_cards=need_this_keyword,
        )

        if not args.no_detail:
            enriched = []
            for i, card in enumerate(cards, 1):
                if remaining is not None and remaining <= 0:
                    break
                print(f"  [DETAIL] {i}/{len(cards)} — {card.get('title','')[:40]}")
                enriched.append(scraper.fetch_detail(card))
                time.sleep(2.0 if not args.fast else 0.45)
                if remaining is not None:
                    remaining -= 1
            all_raw.extend(enriched)
        else:
            if remaining is not None:
                cards = cards[:remaining]
            all_raw.extend(cards)
            if remaining is not None:
                remaining -= len(cards)

    scraper.close()

    if not all_raw:
        print("[WARN] No posts scraped. Check keyword / login.")
        sys.exit(0)

    # Drop duplicates already on disk (append mode)
    if existing_links:
        before = len(all_raw)
        all_raw = [
            p
            for p in all_raw
            if str(p.get("post_link", "") or "").strip() not in existing_links
        ]
        print(f"[APPEND] Removed {before - len(all_raw)} duplicate(s) already in dataset")

    if not all_raw:
        print("[WARN] No new unique posts after dedupe. Nothing to save.")
        sys.exit(0)

    print(f"\n[INFO] New posts to add: {len(all_raw)}")

    start_index = max_live_numeric_id(existing_processed) + 1 if existing_processed else 1

    raw_records, processed_records = build_records(
        all_raw,
        category=args.category,
        do_caption=not args.no_caption,
        start_index=start_index,
    )

    if args.append and (existing_processed or existing_raw):
        raw_records = existing_raw + raw_records
        processed_records = existing_processed + processed_records
        print(
            f"[APPEND] Total after merge: {len(processed_records)} processed, "
            f"{len(raw_records)} raw rows"
        )

    # Save raw (completely untouched)
    with open(RAW_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(raw_records, f, ensure_ascii=False, indent=2)
    print(f"\n[SAVED] Raw archive   → {RAW_OUTPUT_PATH}")

    # Save processed (anonymized + AI-enriched) → trend builder reads this
    with open(PROCESSED_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(processed_records, f, ensure_ascii=False, indent=2)
    print(f"[SAVED] Trend input   → {PROCESSED_OUTPUT_PATH}")

    # ── Supabase sync ──────────────────────────────────────────────
    run_id = datetime.utcnow().strftime("scrape_%Y%m%d_%H%M%S")
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from supabase_writer import write_posts
        from supabase_client import is_configured
        if is_configured():
            print(f"\n[DB] Syncing {len(processed_records)} posts to Supabase…")
            write_posts(run_id, processed_records)
        else:
            print("[DB] Supabase skipped (SUPABASE_PASSWORD not set in .env)")
    except Exception as e:
        print(f"[DB WARN] Supabase sync skipped: {e}")

    print("\n[NEXT] Run:  .venv/bin/python3 xhs_trend_builder.py")


if __name__ == "__main__":
    main()
