#!/usr/bin/env python3
"""
XHS Scraper — Playwright edition
=================================
Drop-in replacement for xhs_scraper_live.py using Playwright instead of
DrissionPage. Same output format (data/xhs_raw_posts.json + data/xhs_posts.json).

USAGE
  cd module_1
  .venv/bin/python3 xhs_scraper_pw.py --keywords "Celine" "Celine穿搭" --times 2
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
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

# ── Load .env ──────────────────────────────────────────────────────
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
VISION_MODEL = os.environ.get("DEFAULT_MODEL", "openai/gpt-4o-mini")

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
RAW_OUTPUT_PATH = DATA_DIR / "xhs_raw_posts.json"
PROCESSED_OUTPUT_PATH = DATA_DIR / "xhs_posts.json"

XHS_EXPLORE_URL = "https://www.xiaohongshu.com/explore"
XHS_SEARCH_URL = "https://www.xiaohongshu.com/search_result?keyword={keyword}&type=51"


# ── Helpers ────────────────────────────────────────────────────────
def anonymize_creator(username: str) -> str:
    h = hashlib.sha256(username.encode("utf-8")).hexdigest()[:8]
    return f"user_{h}"


def _parse_count(text: str) -> int:
    if not text:
        return 0
    text = text.strip().replace(",", "").replace(" ", "")
    if "万" in text:
        try:
            return int(float(text.replace("万", "")) * 10000)
        except ValueError:
            return 0
    m = re.search(r"(\d+)", text)
    return int(m.group(1)) if m else 0


def _parse_hashtags(text: str) -> list[str]:
    return re.findall(r"#[^\s#]+", text)


# ── AI image captioning ───────────────────────────────────────────
def caption_image(image_url: str, title: str = "") -> str:
    if not OPENROUTER_API_KEY:
        return "[skipped: no API key]"
    try:
        req = urllib.request.Request(image_url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.xiaohongshu.com/",
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            b64 = base64.b64encode(r.read()).decode()
    except Exception as e:
        return f"[skipped: image download failed: {e}]"

    ext = image_url.split("?")[0].rsplit(".", 1)[-1].lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "webp": "image/webp"}.get(ext, "image/jpeg")

    payload = json.dumps({
        "model": VISION_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": (
                    f"You are analyzing a Xiaohongshu post image for trend research.\n"
                    f"Post title: \"{title}\"\n\n"
                    "In 2-3 sentences describe: products shown, visual aesthetic, "
                    "colors, styling, any visible text or branding. Be specific, factual."
                )},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ],
        }],
        "max_tokens": 300,
    }).encode()

    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read())
        return resp["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[caption error: {e}]"


# ── Playwright Scraper ─────────────────────────────────────────────
class XHSPlaywrightScraper:
    def __init__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        # persistent context keeps cookies across runs (no re-login every time)
        user_data = str(Path(__file__).parent / ".pw_profile")
        self.context = self._pw.chromium.launch_persistent_context(
            user_data,
            headless=False,
            viewport={"width": 1280, "height": 900},
            locale="zh-CN",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()

    def ensure_login(self):
        self.page.goto(XHS_EXPLORE_URL, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        # Always pause for login — let the user scan QR if needed
        print("\n" + "=" * 50)
        print("  Browser is open at xiaohongshu.com")
        print("  If you see a QR code → scan it with your XHS app")
        print("  If already logged in → just press Enter")
        print("=" * 50)
        input("\n  Press ENTER when you're logged in and ready → ")
        print("[LOGIN] Continuing with scrape…")
        time.sleep(2)

    def search(self, keyword: str, scroll_times: int = 2,
               filter_words: list[str] | None = None) -> list[dict]:
        url = XHS_SEARCH_URL.format(keyword=quote(keyword))
        print(f"  [SEARCH] {url}")
        self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(4)

        cards: list[dict] = []
        seen_links: set[str] = set()

        for scroll_n in range(scroll_times):
            print(f"  [SCROLL] {scroll_n + 1}/{scroll_times}")
            new_cards = self._extract_cards(keyword)
            for c in new_cards:
                link = c.get("post_link", "")
                if not link or link in seen_links:
                    continue
                if filter_words:
                    title_lower = (c.get("title") or "").lower()
                    if not any(w.lower() in title_lower for w in filter_words):
                        continue
                seen_links.add(link)
                cards.append(c)
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(3)

        print(f"  [FOUND] {len(cards)} cards for '{keyword}'")
        return cards

    def _extract_cards(self, keyword: str) -> list[dict]:
        results = []
        # XHS search result selectors
        sections = self.page.locator("section.note-item")
        count = sections.count()
        if count == 0:
            sections = self.page.locator(".feeds-container .note-item")
            count = sections.count()

        for i in range(count):
            try:
                sec = sections.nth(i)
                # post link
                link_el = sec.locator("a").first
                href = link_el.get_attribute("href") or ""
                if href and href.startswith("/"):
                    href = "https://www.xiaohongshu.com" + href
                if not href:
                    continue

                # cover image
                img_el = sec.locator("img").first
                cover_url = ""
                if img_el.count() > 0:
                    cover_url = img_el.get_attribute("src") or img_el.get_attribute("data-src") or ""

                # footer: title, creator, likes
                footer = sec.locator(".footer")
                title = ""
                creator = ""
                likes = "0"
                if footer.count() > 0:
                    t = footer.locator(".title")
                    title = t.inner_text() if t.count() > 0 else ""
                    n = footer.locator(".author-wrapper .name, .name")
                    creator = n.first.inner_text() if n.count() > 0 else ""
                    lw = footer.locator(".like-wrapper span, .like-wrapper .count, .like-wrapper")
                    likes = lw.first.inner_text() if lw.count() > 0 else "0"

                results.append({
                    "keyword": keyword,
                    "post_link": href,
                    "title": title.strip(),
                    "raw_creator": creator.strip(),
                    "likes": _parse_count(likes),
                    "cover_url": cover_url,
                })
            except Exception as e:
                continue
        return results

    def fetch_details_batch(self, posts: list[dict], max_tabs: int = 5) -> list[dict]:
        """Fetch detail pages for multiple posts in parallel using multiple tabs."""
        results = []
        batch_size = max_tabs

        for batch_start in range(0, len(posts), batch_size):
            batch = posts[batch_start:batch_start + batch_size]
            tabs = []
            # Open all tabs at once
            for post in batch:
                link = post.get("post_link", "")
                if not link:
                    results.append(_fill_defaults(post))
                    continue
                try:
                    page = self.context.new_page()
                    page.goto(link, wait_until="domcontentloaded", timeout=15000)
                    tabs.append((page, post))
                except Exception as e:
                    print(f"    [WARN] Tab open failed: {str(e)[:50]}")
                    results.append(_fill_defaults(post))

            # Wait for all tabs to load
            time.sleep(3)

            # Extract data from each tab
            for page, post in tabs:
                try:
                    post = self._extract_detail_from_page(page, post)
                except Exception as e:
                    print(f"    [WARN] Detail failed: {str(e)[:50]}")
                    post = _fill_defaults(post)
                finally:
                    try:
                        page.close()
                    except Exception:
                        pass
                results.append(post)

            idx_start = batch_start + 1
            idx_end = min(batch_start + batch_size, len(posts))
            print(f"  [BATCH] {idx_start}-{idx_end}/{len(posts)} done")

        return results

    def _extract_detail_from_page(self, detail_page, post: dict) -> dict:
        """Extract all detail data from an already-loaded page."""
        # date
        date_el = detail_page.locator(".date, .note-time, span.publish-date")
        post["date"] = date_el.first.inner_text().strip() if date_el.count() > 0 else ""

        # saves
        saves_el = detail_page.locator(".collect-wrapper .count, [data-type='collect'] .count")
        post["saves"] = _parse_count(saves_el.first.inner_text() if saves_el.count() > 0 else "0")

        # comment count
        comments_el = detail_page.locator(".chat-wrapper .count, [data-type='chat'] .count")
        post["comments"] = _parse_count(comments_el.first.inner_text() if comments_el.count() > 0 else "0")

        # caption
        desc_el = detail_page.locator("#detail-desc, .desc, div.desc")
        raw_desc = ""
        if desc_el.count() > 0:
            raw_desc = desc_el.first.inner_text().strip().replace("\n", " ")
        post["caption"] = raw_desc

        # hashtags
        hashtag_els = detail_page.locator("#hash-tag, a.tag")
        if hashtag_els.count() > 0:
            post["hashtags"] = [hashtag_els.nth(j).inner_text().strip()
                                for j in range(hashtag_els.count())]
        else:
            post["hashtags"] = _parse_hashtags(raw_desc)

        # images
        image_urls: list[str] = []
        img_els = detail_page.locator(".note-image img, .note-slider img, .carousel img")
        for j in range(img_els.count()):
            src = img_els.nth(j).get_attribute("src") or img_els.nth(j).get_attribute("data-src") or ""
            if src and src not in image_urls and "avatar" not in src:
                image_urls.append(src)
        if not image_urls and post.get("cover_url"):
            image_urls = [post["cover_url"]]
        post["all_image_urls"] = image_urls

        # video
        video_el = detail_page.locator("video")
        post["is_video"] = video_el.count() > 0
        if video_el.count() > 0:
            post["video_url"] = video_el.first.get_attribute("src") or ""
            poster = video_el.first.get_attribute("poster") or ""
            if poster and not image_urls:
                post["all_image_urls"] = [poster]
        else:
            post["video_url"] = ""

        # comments — grab what's visible (no extra scrolling for speed)
        post["raw_comments"] = self._scrape_comments(detail_page, max_scrolls=1)

        return post

    def _scrape_comments(self, page, max_scrolls: int = 2) -> list[dict]:
        comments: list[dict] = []
        try:
            # scroll to load comments
            for _ in range(max_scrolls):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1.5)

            items = page.locator(".comment-item, .commentItem, .parent-comment")
            for i in range(items.count()):
                try:
                    item = items.nth(i)
                    text_el = item.locator(".note-text, .content, .comment-content, span").first
                    raw_text = text_el.inner_text().strip() if text_el.count() > 0 else ""
                    if not raw_text:
                        continue

                    name_el = item.locator(".user-info .name, .author, .nickname").first
                    raw_name = name_el.inner_text().strip() if name_el.count() > 0 else f"anon_{i}"

                    like_el = item.locator(".like-wrapper .count, .like-count").first
                    c_likes = _parse_count(like_el.inner_text() if like_el.count() > 0 else "0")

                    # replies
                    replies: list[dict] = []
                    reply_items = item.locator(".reply-item, .sub-comment-item")
                    for j in range(reply_items.count()):
                        try:
                            r = reply_items.nth(j)
                            r_text = r.locator(".note-text, .content, span").first
                            r_txt = r_text.inner_text().strip() if r_text.count() > 0 else ""
                            if not r_txt:
                                continue
                            r_name = r.locator(".user-info .name, .author").first
                            r_nm = r_name.inner_text().strip() if r_name.count() > 0 else f"anon_r{j}"
                            r_like = r.locator(".like-wrapper .count").first
                            r_lk = _parse_count(r_like.inner_text() if r_like.count() > 0 else "0")
                            replies.append({
                                "commenter_id": anonymize_creator(r_nm),
                                "text": r_txt,
                                "likes": r_lk,
                            })
                        except Exception:
                            continue

                    comments.append({
                        "commenter_id": anonymize_creator(raw_name),
                        "text": raw_text,
                        "likes": c_likes,
                        "replies": replies,
                    })
                except Exception:
                    continue
        except Exception:
            pass
        return comments

    def close(self):
        try:
            self.context.close()
            self._pw.stop()
        except Exception:
            pass


def _fill_defaults(post: dict) -> dict:
    post.setdefault("date", "")
    post.setdefault("saves", 0)
    post.setdefault("comments", 0)
    post.setdefault("caption", "")
    post.setdefault("hashtags", [])
    post.setdefault("all_image_urls", [])
    post.setdefault("is_video", False)
    post.setdefault("video_url", "")
    post.setdefault("raw_comments", [])
    return post


# ── Build output records ───────────────────────────────────────────
def build_records(raw_posts, category, do_caption):
    raw_records = []
    processed = []
    for idx, post in enumerate(raw_posts, start=1):
        pid = f"live_{idx:04d}"
        raw_records.append({
            "post_id": pid,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            **post,
        })

        creator_anon = anonymize_creator(post.get("raw_creator") or f"unknown_{idx}")
        all_imgs = post.get("all_image_urls", [])
        first_img = next((u for u in all_imgs if u), post.get("cover_url", ""))
        ai_caption = ""
        if do_caption and first_img:
            print(f"  [AI] Captioning image for post {pid}…")
            ai_caption = caption_image(first_img, post.get("title", ""))
            time.sleep(0.4)

        comments_data = post.get("raw_comments", [])
        processed.append({
            "post_id": pid,
            "keyword": post.get("keyword", ""),
            "category": category,
            "date": post.get("date", ""),
            "title": post.get("title", ""),
            "caption": post.get("caption", ""),
            "hashtags": post.get("hashtags", []),
            "likes": post.get("likes", 0),
            "comment_count": post.get("comments", 0),
            "saves": post.get("saves", 0),
            "creator": creator_anon,
            "post_link": post.get("post_link", ""),
            "all_image_urls": all_imgs,
            "cover_url": post.get("cover_url", ""),
            "is_video": post.get("is_video", False),
            "video_url": post.get("video_url", ""),
            "image_caption": ai_caption,
            "comments_scraped": comments_data,
            "comments_count_scraped": len(comments_data),
        })
    return raw_records, processed


# ── Main ───────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="XHS scraper (Playwright)")
    parser.add_argument("--keywords", "-k", nargs="+", required=True)
    parser.add_argument("--times", "-t", type=int, default=2)
    parser.add_argument("--category", "-c", default="luxury_fashion")
    parser.add_argument("--filter", "-f", nargs="*", dest="filter_words")
    parser.add_argument("--no-detail", action="store_true")
    parser.add_argument("--no-caption", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("XHS Scraper — Playwright edition")
    print(f"Keywords  : {args.keywords}")
    print(f"Scroll×   : {args.times} per keyword")
    print(f"Category  : {args.category}")
    print(f"Filter    : {args.filter_words or 'none'}")
    print(f"Detail    : {not args.no_detail}")
    print(f"AI caption: {not args.no_caption}")
    print("=" * 60)

    scraper = XHSPlaywrightScraper()
    scraper.ensure_login()

    all_raw: list[dict] = []

    def _save_raw_quick():
        """Save raw data INSTANTLY — no captioning, no processing. Cannot lose data."""
        if not all_raw:
            return
        # Save raw dump immediately (fast — just JSON serialize)
        RAW_OUTPUT_PATH.write_text(
            json.dumps(all_raw, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # Also save a quick processed version WITHOUT AI captioning
        quick_processed = []
        for idx, post in enumerate(all_raw, start=1):
            pid = f"live_{idx:04d}"
            quick_processed.append({
                "post_id": pid,
                "keyword": post.get("keyword", ""),
                "category": args.category,
                "date": post.get("date", ""),
                "title": post.get("title", ""),
                "caption": post.get("caption", ""),
                "hashtags": post.get("hashtags", []),
                "likes": post.get("likes", 0),
                "comment_count": post.get("comments", 0),
                "saves": post.get("saves", 0),
                "creator": anonymize_creator(post.get("raw_creator") or f"unknown_{idx}"),
                "post_link": post.get("post_link", ""),
                "all_image_urls": post.get("all_image_urls", []),
                "cover_url": post.get("cover_url", ""),
                "is_video": post.get("is_video", False),
                "video_url": post.get("video_url", ""),
                "image_caption": "",
                "comments_scraped": post.get("raw_comments", []),
                "comments_count_scraped": len(post.get("raw_comments", [])),
            })
        PROCESSED_OUTPUT_PATH.write_text(
            json.dumps(quick_processed, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  [SAVED] {len(all_raw)} posts → {PROCESSED_OUTPUT_PATH.name}")

    try:
        for kw_idx, kw in enumerate(args.keywords, 1):
            print(f"\n[KEYWORD {kw_idx}/{len(args.keywords)}] {kw}")
            cards = scraper.search(kw, scroll_times=args.times,
                                   filter_words=args.filter_words or None)

            if not args.no_detail:
                enriched = scraper.fetch_details_batch(cards, max_tabs=5)
                all_raw.extend(enriched)
            else:
                all_raw.extend(cards)

            # Save INSTANTLY after each keyword — no captioning, just raw data
            _save_raw_quick()

    except KeyboardInterrupt:
        print(f"\n\n[STOPPED] Ctrl+C — saving {len(all_raw)} posts…")
        _save_raw_quick()
        scraper.close()
        print(f"[DONE] Data saved! Run 'python3 xhs_trend_builder.py' to build trends.")
        sys.exit(0)

    scraper.close()

    if not all_raw:
        print("[WARN] No posts scraped.")
        sys.exit(0)

    print(f"\n[INFO] Total posts scraped: {len(all_raw)}")
    print(f"[INFO] AI captioning {len(all_raw)} posts (this takes a few minutes)…")

    # Now do the full build with AI captioning
    raw_records, processed_records = build_records(
        all_raw, args.category, do_caption=not args.no_caption,
    )
    RAW_OUTPUT_PATH.write_text(json.dumps(raw_records, ensure_ascii=False, indent=2), encoding="utf-8")
    PROCESSED_OUTPUT_PATH.write_text(json.dumps(processed_records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[SAVED] Final processed posts → {PROCESSED_OUTPUT_PATH}  ({len(processed_records)} records)")

    print(f"\nDone! Run 'python3 xhs_trend_builder.py' to build trend objects.")


if __name__ == "__main__":
    main()
