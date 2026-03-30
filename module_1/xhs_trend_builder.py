#!/usr/bin/env python3
"""XHS Trend Object Builder (Week 9 Module 1 MVP).

Local, no-notebook script that:
1) loads posts + run config,
2) retrieves records for brand/category/time window,
3) clusters similar posts into trends,
4) writes structured trend objects,
5) writes run log and reviewer feedback template.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


DEFAULT_POSTS_PATH = "data/xhs_posts.json"
DEFAULT_CONFIG_PATH = "data/run_config.json"
DEFAULT_OUTPUT_DIR = "outputs"


STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "you",
    "are",
    "too",
    "very",
    "真的",
    "就是",
    "一个",
    "一下",
    "可以",
    "分享",
    "我的",
    "我们",
    "这个",
    "一样",
}


class CliTrace:
    """Terminal styling + trace capture."""

    RESET = "\033[0m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"

    def __init__(self, pretty: bool = True, min_stage_seconds: float = 0.0) -> None:
        self.pretty = pretty
        self.min_stage_seconds = max(0.0, float(min_stage_seconds))
        self.events: List[Dict[str, Any]] = []

    def _style(self, text: str, code: str) -> str:
        if not self.pretty:
            return text
        return f"{code}{text}{self.RESET}"

    def _emit(self, level: str, step: str, message: str, meta: Optional[Dict[str, Any]] = None) -> None:
        ts = datetime.now(UTC).isoformat()
        self.events.append(
            {
                "timestamp_utc": ts,
                "level": level,
                "step": step,
                "message": message,
                "meta": meta or {},
            }
        )
        level_map = {
            "stage": self._style("●", self.CYAN),
            "ok": self._style("✓", self.GREEN),
            "warn": self._style("!", self.YELLOW),
            "error": self._style("x", self.RED),
            "info": self._style("·", self.DIM),
        }
        badge = level_map.get(level, "-")
        print(f"{badge} [{step}] {message}")

    def stage(self, step: str, message: str, meta: Optional[Dict[str, Any]] = None) -> None:
        self._emit("stage", step, message, meta)

    def ok(self, step: str, message: str, meta: Optional[Dict[str, Any]] = None) -> None:
        self._emit("ok", step, message, meta)

    def warn(self, step: str, message: str, meta: Optional[Dict[str, Any]] = None) -> None:
        self._emit("warn", step, message, meta)

    def info(self, step: str, message: str, meta: Optional[Dict[str, Any]] = None) -> None:
        self._emit("info", step, message, meta)

    def error(self, step: str, message: str, meta: Optional[Dict[str, Any]] = None) -> None:
        self._emit("error", step, message, meta)

    def banner(self, title: str) -> None:
        line = "=" * max(20, len(title) + 6)
        print(self._style(line, self.MAGENTA))
        print(self._style(f"  {title}", self.BOLD + self.MAGENTA))
        print(self._style(line, self.MAGENTA))

    def _spinner(self, step: str, message: str, done: threading.Event) -> None:
        if not (self.pretty and sys.stdout.isatty()):
            return
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        idx = 0
        while not done.is_set():
            frame = self._style(frames[idx % len(frames)], self.BLUE)
            text = f"\r{frame} [{step}] {message}"
            print(text, end="", flush=True)
            time.sleep(0.09)
            idx += 1
        print("\r" + (" " * (len(message) + len(step) + 12)) + "\r", end="", flush=True)

    def run_stage(self, step: str, message: str, fn: Callable[[], Any]) -> Any:
        self.stage(step, message)
        done = threading.Event()
        worker = threading.Thread(target=self._spinner, args=(step, message, done), daemon=True)
        worker.start()
        started = time.time()
        try:
            result = fn()
        except Exception as exc:
            done.set()
            worker.join(timeout=0.2)
            elapsed = time.time() - started
            self.error(step, f"Failed after {elapsed:.2f}s: {exc}")
            raise
        # Optional live-demo pacing: keep spinner visible a bit longer per stage.
        elapsed = time.time() - started
        if self.min_stage_seconds > elapsed:
            time.sleep(self.min_stage_seconds - elapsed)
        done.set()
        worker.join(timeout=0.2)
        elapsed = time.time() - started
        self.ok(step, f"Completed in {elapsed:.2f}s")
        return result

    def save(self, path: Path) -> None:
        with path.open("w", encoding="utf-8") as f:
            for event in self.events:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")


@dataclass
class Post:
    post_id: str
    brand: str
    category: str
    date: str
    title: str
    caption: str
    hashtags: List[str]
    likes: int
    comments: int
    saves: int
    creator: str
    # enriched fields from live scraper
    post_link: str = ""
    cover_url: str = ""
    all_image_urls: List[str] = None        # type: ignore[assignment]
    is_video: bool = False
    video_url: str = ""
    image_caption: str = ""                 # AI-generated image description
    keyword: str = ""
    comments_scraped: List[Dict[str, Any]] = None   # type: ignore[assignment]
    comments_count_scraped: int = 0

    def __post_init__(self):
        if self.all_image_urls is None:
            self.all_image_urls = []
        if self.comments_scraped is None:
            self.comments_scraped = []

    @property
    def engagement(self) -> int:
        return self.likes + self.comments + self.saves

    @property
    def first_image_url(self) -> str:
        """Return the best available image URL for this post."""
        if self.all_image_urls:
            return self.all_image_urls[0]
        return self.cover_url or ""


def load_dotenv_file(dotenv_path: Path) -> None:
    """Minimal .env loader so this script stays dependency-light."""
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def normalize_posts(raw_posts: List[Dict[str, Any]]) -> List[Post]:
    posts: List[Post] = []
    for i, item in enumerate(raw_posts, start=1):
        post_id = str(item.get("post_id") or f"p{i:03d}")
        all_imgs = list(item.get("all_image_urls", []) or [])
        posts.append(
            Post(
                post_id=post_id,
                brand=str(item.get("brand", item.get("keyword", ""))).strip(),
                category=str(item.get("category", "")).strip(),
                date=str(item.get("date", "")).strip(),
                title=str(item.get("title", "")).strip(),
                caption=str(item.get("caption", "")).strip(),
                hashtags=list(item.get("hashtags", []) or []),
                likes=safe_int(item.get("likes")),
                comments=safe_int(item.get("comments")),
                saves=safe_int(item.get("saves")),
                creator=str(item.get("creator", "")).strip(),
                # enriched fields
                post_link=str(item.get("post_link", "")).strip(),
                cover_url=str(item.get("cover_url", "")).strip(),
                all_image_urls=all_imgs,
                is_video=bool(item.get("is_video", False)),
                video_url=str(item.get("video_url", "")).strip(),
                image_caption=str(item.get("image_caption", "")).strip(),
                keyword=str(item.get("keyword", "")).strip(),
                comments_scraped=list(item.get("comments_scraped", []) or []),
                comments_count_scraped=safe_int(item.get("comments_count_scraped", 0)),
            )
        )
    return [p for p in posts if p.title]


def parse_iso_date(date_text: str) -> Optional[datetime]:
    try:
        return datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        return None


def post_matches_filters(post: Post, config: Dict[str, Any]) -> bool:
    brand = str(config.get("brand", "ALL")).strip().lower()
    category = str(config.get("category", "")).strip().lower()
    time_window = config.get("time_window", {}) or {}
    start_date = parse_iso_date(str(time_window.get("start_date", "")).strip())
    end_date = parse_iso_date(str(time_window.get("end_date", "")).strip())
    post_date = parse_iso_date(post.date)

    brand_ok = True if brand in {"", "all", "*"} else post.brand.lower() == brand
    category_ok = True if not category else post.category.lower() == category

    date_ok = True
    if post_date and start_date:
        date_ok = date_ok and (post_date >= start_date)
    if post_date and end_date:
        date_ok = date_ok and (post_date <= end_date)

    return brand_ok and category_ok and date_ok


def tokenize(post: Post) -> List[str]:
    text = f"{post.title} {post.caption} {' '.join(post.hashtags)}".lower()
    zh_chunks = re.findall(r"[\u4e00-\u9fff]{2,8}", text)
    en_chunks = re.findall(r"[a-zA-Z][a-zA-Z0-9\-_]{1,20}", text)

    tokens: List[str] = []
    for tok in zh_chunks + en_chunks:
        tok = tok.strip().lstrip("#")
        if not tok or tok in STOPWORDS:
            continue
        tokens.append(tok)
    return tokens


def jaccard(tokens_a: List[str], tokens_b: List[str]) -> float:
    set_a, set_b = set(tokens_a), set(tokens_b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def build_clusters(posts: List[Post], token_map: Dict[str, List[str]]) -> List[List[Post]]:
    visited: set[str] = set()
    clusters: List[List[Post]] = []

    for post in posts:
        if post.post_id in visited:
            continue

        queue = [post]
        visited.add(post.post_id)
        component: List[Post] = []

        while queue:
            current = queue.pop(0)
            component.append(current)
            current_tokens = token_map[current.post_id]

            for other in posts:
                if other.post_id in visited:
                    continue
                other_tokens = token_map[other.post_id]
                score = jaccard(current_tokens, other_tokens)
                overlap = len(set(current_tokens) & set(other_tokens))
                if score >= 0.35 and overlap >= 4:
                    visited.add(other.post_id)
                    queue.append(other)

        clusters.append(component)

    clusters.sort(key=lambda c: sum(p.engagement for p in c), reverse=True)
    return clusters


def label_from_tokens(tokens: List[str]) -> str:
    joined = " ".join(tokens)
    # ── Luxury fashion / leather goods labels ──────────────────────────
    if any(k in joined for k in ["静奢", "quiet luxury", "old money", "老钱", "低调奢华"]):
        return "Quiet Luxury / Old Money Aesthetic"
    if any(k in joined for k in ["极简", "minimalis", "less is more", "剪裁", "版型"]):
        return "Minimalist Tailoring & Structure"
    if any(k in joined for k in ["包包", "手袋", "box", "triomphe", "cabas", "皮具"]):
        return "Luxury Handbag & Leather Goods"
    if any(k in joined for k in ["通勤", "职场", "power dress", "西装", "办公"]):
        return "Power Dressing & Workwear"
    if any(k in joined for k in ["穿搭", "搭配", "look", "春夏", "春装", "衣橱"]):
        return "Seasonal Styling & Capsule Wardrobe"
    if any(k in joined for k in ["面料", "开司米", "cashmere", "亚麻", "工艺", "纺织"]):
        return "Fabric Craft & Material Appreciation"
    if any(k in joined for k in ["街拍", "安福路", "上海", "恒隆", "旗舰"]):
        return "Shanghai Luxury Street Style"
    # ── Beauty labels ──────────────────────────────────────────────────
    if any(k in joined for k in ["y3k", "液态金属", "全息", "chrome", "偏光"]):
        return "Y3K Futuristic Makeup Aesthetic"
    if any(k in joined for k in ["情绪护肤", "神经美容", "香氛", "疗愈", "安定感"]):
        return "Emotional Wellness Skincare"
    if any(k in joined for k in ["场景护肤", "机舱", "急救"]):
        return "Scenario-Based Skincare Routines"
    if any(k in joined for k in ["微瑕", "活人感", "柔焦", "原生感"]):
        return "Real-Skin Imperfection Makeup"
    if any(k in joined for k in ["pdrn", "外泌体", "再生医学", "胶原", "干细胞"]):
        return "Regenerative Biotech Skincare"
    return "Mixed Trend Signals"


def summarize_cluster(label: str, posts: List[Post]) -> str:
    titles = "；".join(p.title for p in posts[:2])
    return f"Posts cluster around {label.lower()} with recurring evidence such as: {titles}."


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def next_run_label(output_dir: Path) -> str:
    counter_path = output_dir / "run_counter.json"
    current = 0
    if counter_path.exists():
        try:
            data = json.loads(counter_path.read_text(encoding="utf-8"))
            current = int(data.get("last_run_number", 0))
        except Exception:
            current = 0
    new_num = current + 1
    counter_payload = {
        "last_run_number": new_num,
        "updated_at_utc": datetime.now(UTC).isoformat(),
    }
    counter_path.write_text(json.dumps(counter_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return f"run_{new_num:04d}"


def trend_output_schema() -> Dict[str, Any]:
    return {
        "schema_name": "xhs_trend_object_run_schema",
        "schema_version": "1.0.0",
        "description": "Type-B reviewable output for Module 1 Trend Object Builder.",
        "top_level_fields": [
            "run_id",
            "agent",
            "decision",
            "retrieval",
            "output_type",
            "time_window",
            "generated_at_utc",
            "trend_objects",
        ],
        "trend_object_fields": [
            "trend_id",
            "label",
            "category",
            "summary",
            "ai_reasoning",
            "confidence",
            "labeling_source",
            "evidence",
            "metrics",
            "visual_assets",
            "timestamp",
        ],
        "evidence_fields": [
            "post_ids", "snippets", "posts",
        ],
        "evidence_post_fields": [
            "post_id", "title", "date", "brand", "likes", "comments", "saves",
            "creator", "post_link", "cover_url", "all_image_urls",
            "is_video", "video_url", "image_caption",
        ],
        "metrics_fields": [
            "post_count",
            "total_engagement",
            "avg_engagement",
            "total_likes",
            "total_comments",
            "total_saves",
            "top_keywords",
            "video_post_count",
            "image_count",
        ],
        "visual_assets_fields": [
            "all_image_urls",     # all image URLs across every post in the trend
            "image_captions",     # list of {post_id, caption} AI descriptions
            "video_post_count",   # how many posts in trend are videos
        ],
        "comment_signals_fields": [
            "total_comments_scraped",   # count of top-level comments collected
            "total_replies_scraped",    # count of replies collected
            "all_comments",             # list of {post_id, commenter_id, text, likes, replies:[{commenter_id, text, likes}]}
        ],
        "privacy_note": (
            "Commenter real usernames are NEVER stored. "
            "Each commenter_id is a one-way SHA-256 hash so the same user "
            "maps to the same ID without being reversible."
        ),
    }


def maybe_label_with_llm(
    posts: List[Post],
    base_prompt: str,
    fallback_label: str,
    fallback_summary: str,
    fallback_confidence: str,
    fallback_reasoning: str,
    llm_enabled: bool,
    llm_model: str,
    llm_errors: Optional[List[str]] = None,
) -> Tuple[str, str, str, str, str]:
    if not llm_enabled:
        return fallback_label, fallback_summary, fallback_confidence, "heuristic", fallback_reasoning

    api_key = os.getenv("OPENROUTER_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
    api_key = api_key.strip()
    if not api_key:
        if llm_errors is not None:
            llm_errors.append("OPENROUTER_API_KEY missing")
        return fallback_label, fallback_summary, fallback_confidence, "heuristic", fallback_reasoning

    try:
        from openai import OpenAI  # imported lazily to keep base path simple
    except Exception as e:
        if llm_errors is not None:
            llm_errors.append(f"openai import failed: {e}")
        return fallback_label, fallback_summary, fallback_confidence, "heuristic", fallback_reasoning

    titles = [p.title for p in posts[:12]]
    prompt = (
        "You are an XHS (Xiaohongshu) trend analyst.\n\n"
        "PRIMARY ASSIGNMENT PROMPT (must follow):\n"
        f"{base_prompt}\n\n"
        "CLUSTER LABELING TASK:\n"
        "Given these XHS post titles from one cluster, identify the XHS CONTENT TREND — "
        "what are users creating content about? What discourse pattern is this?\n\n"
        "Return strict JSON with keys: label, summary, confidence, ai_reasoning.\n"
        "Rules:\n"
        "- Label must describe the XHS USER CONTENT PATTERN (e.g. 'Old Celine vs New Celine Nostalgia Debate', "
        "'Box Bag Still Worth It Discourse', 'Celebrity Outfit Analysis Content', "
        "'Cross-Border Luxury Deal Sharing', 'Soft 16 Daily Commute Reviews').\n"
        "- Do NOT use generic labels like 'Brand Loyalty', 'Fashion Highlights', 'Handbag Collection'.\n"
        "- Summary: what are XHS users posting/discussing/debating in this cluster?\n"
        "- Confidence: low/medium/high.\n\n"
        f"Titles:\n{json.dumps(titles, ensure_ascii=False, indent=2)}"
    )
    try:
        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        response = client.responses.create(model=llm_model, input=prompt)
        output_text = getattr(response, "output_text", "") or ""
        parsed = extract_json_object(output_text)
        if not parsed:
            if llm_errors is not None:
                llm_errors.append("LLM response JSON parse failed")
            return fallback_label, fallback_summary, fallback_confidence, "heuristic", fallback_reasoning
        label = str(parsed.get("label") or fallback_label).strip()
        summary = str(parsed.get("summary") or fallback_summary).strip()
        ai_reasoning = str(parsed.get("ai_reasoning") or fallback_reasoning).strip()
        confidence = str(parsed.get("confidence") or fallback_confidence).strip().lower()
        if confidence not in {"low", "medium", "high"}:
            confidence = fallback_confidence
        return label, summary, confidence, "llm", ai_reasoning
    except Exception as e:
        if llm_errors is not None:
            llm_errors.append(f"openai call failed: {e}")
        return fallback_label, fallback_summary, fallback_confidence, "heuristic", fallback_reasoning


def confidence_for_cluster(posts: List[Post], token_map: Dict[str, List[str]]) -> str:
    if len(posts) <= 1:
        return "low"

    similarities: List[float] = []
    for i in range(len(posts)):
        for j in range(i + 1, len(posts)):
            similarities.append(jaccard(token_map[posts[i].post_id], token_map[posts[j].post_id]))

    avg_sim = sum(similarities) / len(similarities) if similarities else 0.0

    token_counter = Counter()
    for p in posts:
        token_counter.update(token_map[p.post_id])
    shared_token_count = sum(1 for _, count in token_counter.items() if count >= 2)

    if len(posts) >= 4 and (avg_sim >= 0.08 or shared_token_count >= 4):
        return "high"
    if len(posts) >= 2 and (avg_sim >= 0.05 or shared_token_count >= 2):
        return "medium"
    return "low"


def to_trend_object(
    trend_idx: int,
    posts: List[Post],
    token_map: Dict[str, List[str]],
    category: str,
    base_prompt: str,
    llm_enabled: bool,
    llm_model: str,
    llm_errors: Optional[List[str]],
) -> Dict[str, Any]:
    token_counter = Counter()
    for p in posts:
        token_counter.update(token_map[p.post_id])
    top_tokens = [t for t, _ in token_counter.most_common(8)]

    # Check if LLM already assigned labels during clustering
    llm_label = getattr(posts[0], '_llm_trend_label', '') if posts else ''
    if llm_label:
        label = llm_label
        summary = getattr(posts[0], '_llm_trend_summary', '')
        confidence = getattr(posts[0], '_llm_trend_confidence', 'medium')
        ai_reasoning = getattr(posts[0], '_llm_trend_reasoning', '')
        labeling_source = "llm"
    else:
        heuristic_label = label_from_tokens(top_tokens)
        heuristic_confidence = confidence_for_cluster(posts, token_map)
        heuristic_summary = summarize_cluster(heuristic_label, posts)
        heuristic_reasoning = (
            f"Grouped because posts share recurring keywords/themes {top_tokens[:5]} and show consistent "
            f"engagement patterns in the same category."
        )
        label, summary, confidence, labeling_source, ai_reasoning = maybe_label_with_llm(
            posts=posts,
            base_prompt=base_prompt,
            fallback_label=heuristic_label,
            fallback_summary=heuristic_summary,
            fallback_confidence=heuristic_confidence,
            fallback_reasoning=heuristic_reasoning,
            llm_enabled=llm_enabled,
            llm_model=llm_model,
            llm_errors=llm_errors,
        )
    total_likes = sum(p.likes for p in posts)
    total_comments = sum(p.comments for p in posts)
    total_saves = sum(p.saves for p in posts)
    total_engagement = total_likes + total_comments + total_saves
    post_count = len(posts)

    evidence_posts = sorted(posts, key=lambda p: p.engagement, reverse=True)[:5]
    evidence = {
        "post_ids": [p.post_id for p in evidence_posts],
        "snippets": [p.title for p in evidence_posts],
        "posts": [
            {
                "post_id":               p.post_id,
                "title":                 p.title,
                "date":                  p.date,
                "brand":                 p.brand,
                "likes":                 p.likes,
                "comments":              p.comments,
                "saves":                 p.saves,
                "creator":               p.creator,
                "post_link":             p.post_link,
                "cover_url":             p.cover_url,
                "all_image_urls":        p.all_image_urls,
                "is_video":              p.is_video,
                "video_url":             p.video_url,
                "image_caption":         p.image_caption,
                "comments_scraped":      p.comments_scraped,        # full comment list
                "comments_count_scraped": p.comments_count_scraped,
            }
            for p in evidence_posts
        ],
    }

    # Collect all image URLs + comments across the whole cluster
    all_cluster_images = []
    all_cluster_image_captions = []
    video_count = 0
    all_cluster_comments: list[dict] = []   # flat list of every comment+replies in cluster

    for p in posts:
        all_cluster_images.extend(p.all_image_urls or ([p.cover_url] if p.cover_url else []))
        if p.image_caption:
            all_cluster_image_captions.append({"post_id": p.post_id, "caption": p.image_caption})
        if p.is_video:
            video_count += 1
        # Attach post_id so we know which post each comment belongs to
        for c in (p.comments_scraped or []):
            all_cluster_comments.append({**c, "post_id": p.post_id})

    # Build comment_signals: top-level view of comment text across the cluster
    flat_comment_texts = [c["text"] for c in all_cluster_comments if c.get("text")]
    flat_reply_texts   = [
        r["text"]
        for c in all_cluster_comments
        for r in c.get("replies", [])
        if r.get("text")
    ]
    total_comments_scraped = len(flat_comment_texts)
    total_replies_scraped  = len(flat_reply_texts)

    metrics = {
        "post_count":       post_count,
        "total_engagement": total_engagement,
        "avg_engagement":   round(total_engagement / post_count, 2) if post_count else 0,
        "total_likes":      total_likes,
        "total_comments":   total_comments,
        "total_saves":      total_saves,
        "top_keywords":     top_tokens[:5],
        "video_post_count": video_count,
        "image_count":      len(all_cluster_images),
    }

    return {
        "trend_id":        f"t{trend_idx:02d}",
        "label":           label,
        "category":        category,
        "summary":         summary,
        "ai_reasoning":    ai_reasoning,
        "confidence":      confidence,
        "labeling_source": labeling_source,
        "evidence":        evidence,
        "metrics":         metrics,
        "timestamp":       datetime.now(UTC).isoformat(),
        # ── visual assets ──────────────────────────────────────────
        "visual_assets": {
            "all_image_urls":   all_cluster_images[:20],
            "image_captions":   all_cluster_image_captions,
            "video_post_count": video_count,
        },
        # ── comment signals ────────────────────────────────────────
        # All comment text is raw/unchanged. Commenter names are NEVER stored
        # — only anonymized SHA-256 IDs. Replies are nested under each comment.
        "comment_signals": {
            "total_comments_scraped": total_comments_scraped,
            "total_replies_scraped":  total_replies_scraped,
            "all_comments": all_cluster_comments,   # [{post_id, commenter_id, text, likes, replies:[...]}, ...]
        },
    }


def build_feedback_template(run_id: str) -> List[Dict[str, Any]]:
    return [
        {
            "reviewer": "Classmate A",
            "run_id": run_id,
            "correctness_quality": 4,
            "missing_info": "yes - consider adding per-trend date span",
            "duplicates_noise": "no",
        },
        {
            "reviewer": "Classmate B",
            "run_id": run_id,
            "correctness_quality": 4,
            "missing_info": "no",
            "duplicates_noise": "yes - one trend may overlap with another",
        },
        {
            "reviewer": "Classmate C",
            "run_id": run_id,
            "correctness_quality": 5,
            "missing_info": "no",
            "duplicates_noise": "no",
        },
    ]


def run(
    posts_path: Path,
    config_path: Path,
    output_dir: Path,
    pretty: bool = True,
    print_json: bool = False,
    llm_test: bool = False,
    live_mode: bool = False,
) -> Tuple[Path, Path, Path, Path]:
    min_stage_seconds = 0.9 if live_mode else 0.0
    cli = CliTrace(pretty=pretty, min_stage_seconds=min_stage_seconds)
    cli.banner("XHS Trend Object Builder")
    if live_mode:
        cli.info("CLI", "Live mode enabled: pacing stage spinner for demo clarity")
    def _load_inputs() -> Tuple[Any, Dict[str, Any]]:
        load_dotenv_file(Path(".env"))
        return read_json(posts_path), read_json(config_path)

    raw_posts, config = cli.run_stage("Prompt", "Loading prompt + config + retrieval sources", _load_inputs)
    output_dir.mkdir(parents=True, exist_ok=True)

    def _retrieve() -> Tuple[List[Post], List[Post], int]:
        all_local_posts = normalize_posts(raw_posts)
        filtered_local = [p for p in all_local_posts if post_matches_filters(p, config)]
        max_local_posts = int(config.get("max_posts", 50))
        filtered_local = sorted(filtered_local, key=lambda p: p.engagement, reverse=True)[:max_local_posts]
        return all_local_posts, filtered_local, max_local_posts

    all_posts, filtered_posts, max_posts = cli.run_stage(
        "Retrieve", "Normalizing and filtering XHS posts", _retrieve
    )
    cli.ok(
        "Retrieve",
        f"Retrieved {len(filtered_posts)} posts from {len(all_posts)} loaded records",
        {"max_posts": max_posts, "posts_path": str(posts_path)},
    )

    def _cluster() -> Tuple[Dict[str, List[str]], List[List[Post]]]:
        token_map_local = {p.post_id: tokenize(p) for p in filtered_posts}

        # Try LLM-first clustering: send all titles to LLM, let it identify trends
        api_key = (os.getenv("OPENROUTER_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")).strip()
        llm_model_c = str(config.get("llm", {}).get("model", "gpt-4.1-mini"))
        llm_enabled_c = config.get("llm", {}).get("enabled", False) and bool(api_key)

        if llm_enabled_c:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")

                # Build post index for LLM
                post_index = []
                for p in filtered_posts:
                    post_index.append({"id": p.post_id, "title": p.title, "likes": p.likes})

                base_prompt_c = str(config.get("prompt", "")).strip()
                llm_cluster_prompt = (
                    f"{base_prompt_c}\n\n"
                    "TASK: Read ALL the XHS post titles below and identify 5-8 distinct XHS CONTENT TRENDS.\n"
                    "For each trend, list which post IDs belong to it.\n\n"
                    "Return ONLY valid JSON array, no markdown:\n"
                    "[{\"trend_label\": \"...\", \"summary\": \"what XHS users are posting/discussing\", "
                    "\"post_ids\": [\"live_0001\", ...], \"confidence\": \"high/medium/low\", "
                    "\"ai_reasoning\": \"why these posts form a trend\"}]\n\n"
                    f"Posts ({len(post_index)} total):\n"
                    f"{json.dumps(post_index, ensure_ascii=False)}"
                )

                response = client.responses.create(model=llm_model_c, input=llm_cluster_prompt)
                output_text = getattr(response, "output_text", "") or ""

                # Parse JSON array from response
                cleaned = output_text.strip()
                if cleaned.startswith("```"):
                    lines = cleaned.split("\n")
                    lines = [l for l in lines if not l.strip().startswith("```")]
                    cleaned = "\n".join(lines).strip()

                parsed_trends = json.loads(cleaned)
                if isinstance(parsed_trends, list) and len(parsed_trends) >= 1:
                    # Build clusters from LLM output
                    post_map = {p.post_id: p for p in filtered_posts}
                    llm_clusters = []
                    for trend_info in parsed_trends:
                        cluster_posts = []
                        for pid in trend_info.get("post_ids", []):
                            if pid in post_map:
                                cluster_posts.append(post_map[pid])
                        if len(cluster_posts) >= 2:
                            # Store LLM label/summary on the first post as metadata
                            cluster_posts[0]._llm_trend_label = trend_info.get("trend_label", "")
                            cluster_posts[0]._llm_trend_summary = trend_info.get("summary", "")
                            cluster_posts[0]._llm_trend_confidence = trend_info.get("confidence", "medium")
                            cluster_posts[0]._llm_trend_reasoning = trend_info.get("ai_reasoning", "")
                            llm_clusters.append(cluster_posts)

                    if llm_clusters:
                        cli.ok("Decide", f"LLM identified {len(llm_clusters)} XHS content trends")
                        return token_map_local, llm_clusters

            except Exception as e:
                cli.warn("Decide", f"LLM clustering failed ({e.__class__.__name__}), falling back to heuristic")

        # Fallback: heuristic clustering
        clusters_local = build_clusters(filtered_posts, token_map_local)
        return token_map_local, clusters_local

    token_map, clusters = cli.run_stage(
        "Decide", "Clustering semantically similar posts into trend candidates", _cluster
    )

    min_posts_per_trend = int(config.get("min_posts_per_trend", 2))
    top_k_trends = int(config.get("top_k_trends", 5))

    selected_clusters = [c for c in clusters if len(c) >= min_posts_per_trend][:top_k_trends]
    if not selected_clusters and clusters:
        selected_clusters = clusters[:1]
        cli.warn(
            "Decide",
            "No cluster met min_posts_per_trend; falling back to top cluster",
            {"min_posts_per_trend": min_posts_per_trend},
        )
    cli.ok("Decide", f"Selected {len(selected_clusters)} trend clusters")

    run_id = next_run_label(output_dir)
    category = str(config.get("category", "unknown"))
    assignment_prompt = str(config.get("prompt", "")).strip()
    prompt_in_use = bool(assignment_prompt)
    if prompt_in_use:
        cli.ok("Prompt", "Assignment prompt found and will be used in decision flow")
    else:
        cli.warn("Prompt", "No prompt found in config; using fallback decision text")
        assignment_prompt = (
            "Given XHS posts for a single brand/category and time window, identify distinct trends "
            "with evidence and confidence."
        )
    llm_config = config.get("llm", {}) or {}
    llm_enabled = bool(llm_config.get("enabled", False))
    llm_model = os.environ.get("DEFAULT_MODEL", str(llm_config.get("model", "gpt-4.1-mini")).strip() or "gpt-4.1-mini")
    llm_errors: List[str] = []

    if llm_test and llm_enabled:
        try:
            from openai import OpenAI

            api_key = (os.getenv("OPENROUTER_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")).strip()
            if not api_key:
                llm_errors.append("LLM test failed: OPENROUTER_API_KEY missing")
                cli.warn("Decide", "LLM test skipped: OPENROUTER_API_KEY missing")
            else:
                def _llm_ping() -> None:
                    client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
                    _ = client.responses.create(
                        model=llm_model,
                        input='Return valid JSON exactly: {"ok": true}',
                    )

                cli.run_stage("Decide", f"Testing live LLM connectivity ({llm_model})", _llm_ping)
                cli.ok("Decide", "LLM connectivity test passed")
        except Exception as e:
            llm_errors.append(f"LLM test failed: {e}")
            cli.warn("Decide", f"LLM connectivity test failed: {e}")

    if llm_enabled:
        cli.info("Decide", f"LLM labeling enabled ({llm_model})")
    else:
        cli.info("Decide", "LLM labeling disabled, using heuristic labels")

    trend_objects = [
        to_trend_object(
            i + 1,
            cluster,
            token_map,
            category,
            assignment_prompt,
            llm_enabled=llm_enabled,
            llm_model=llm_model,
            llm_errors=llm_errors,
        )
        for i, cluster in enumerate(selected_clusters)
    ]
    llm_hits = sum(1 for t in trend_objects if t.get("labeling_source") == "llm")
    cli.ok("Decide", f"Trend objects built ({len(trend_objects)} total, {llm_hits} LLM-labeled)")
    if llm_enabled and llm_hits == 0:
        preview = llm_errors[0] if llm_errors else "No explicit error captured"
        cli.warn("Decide", f"LLM enabled but 0 labels used. First issue: {preview}")

    cli.stage("Output", "Building structured Type-B trend object JSON")
    result = {
        "run_id": run_id,
        "agent": {
            "name": "XHS Trend Object Builder",
            "module": "Module 1 - Trend Object Builder",
            "owner": "Manny",
        },
        "decision": "From XHS posts in a brand/category/time window, produce distinct trend objects with evidence and metrics.",
        "output_type": "Type B - Reviewable output",
        "mvp_outcome_statement": (
            "If our MVP works, trend signals from Xiaohongshu become faster to validate and easier for "
            "downstream teams to reuse, because the system converts raw API/XHS inputs into strict, "
            "evidence-backed Trend Objects."
        ),
        "brand": config.get("brand", "ALL"),
        "category": category,
        "time_window": config.get("time_window", {}),
        "retrieval": {
            "sources": [str(posts_path), str(config_path)],
            "records_loaded": len(all_posts),
            "records_retrieved": len(filtered_posts),
        },
        "prompt": config.get("prompt", ""),
        "prompt_in_use_for_decision": prompt_in_use,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "decision_logic": {
            "mode": "rules-first with optional LLM label/summary",
            "llm_enabled": llm_enabled,
            "llm_model": llm_model if llm_enabled else None,
            "llm_label_calls_succeeded": llm_hits,
            "llm_label_calls_total": len(trend_objects),
            "llm_errors": llm_errors[:20],
        },
        "trend_objects": trend_objects,
    }

    runs_dir = output_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    schema_path = output_dir / "trend_object_schema.json"
    with schema_path.open("w", encoding="utf-8") as f:
        json.dump(trend_output_schema(), f, ensure_ascii=False, indent=2)
    result["schema_file"] = str(schema_path)

    trend_output_path = runs_dir / f"{run_id}_trend_objects.json"
    with trend_output_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    latest_trend_output_path = output_dir / "trend_objects.json"
    with latest_trend_output_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    run_log = {
        "run_id": run_id,
        "retrieved_sources": [str(posts_path), str(config_path)],
        "retrieved_post_ids": [p.post_id for p in filtered_posts],
        "decision_output_file": str(trend_output_path),
        "decision_mode": "rules-first with optional LLM",
        "prompt_in_use_for_decision": prompt_in_use,
        "llm_enabled": llm_enabled,
        "llm_model": llm_model if llm_enabled else None,
        "llm_label_calls_succeeded": llm_hits,
        "llm_label_calls_total": len(trend_objects),
        "llm_errors": llm_errors[:20],
        "evidence_used": {
            t["trend_id"]: t["evidence"]["post_ids"] for t in trend_objects
        },
        "labeling_sources": {t["trend_id"]: t["labeling_source"] for t in trend_objects},
        "confidence": {t["trend_id"]: t["confidence"] for t in trend_objects},
        "next_step_suggestion": "Send approved trend objects into Module 2 for materiality ranking.",
        "timestamp_utc": datetime.now(UTC).isoformat(),
    }

    run_log_path = runs_dir / f"{run_id}_run_log.json"
    with run_log_path.open("w", encoding="utf-8") as f:
        json.dump(run_log, f, ensure_ascii=False, indent=2)
    latest_run_log_path = output_dir / "run_log.json"
    with latest_run_log_path.open("w", encoding="utf-8") as f:
        json.dump(run_log, f, ensure_ascii=False, indent=2)
    cli.ok("Trace/Log", f"Saved run log to {run_log_path}")

    feedback_path = runs_dir / f"{run_id}_feedback.json"
    with feedback_path.open("w", encoding="utf-8") as f:
        json.dump(build_feedback_template(run_id), f, ensure_ascii=False, indent=2)
    latest_feedback_path = output_dir / "feedback_template.json"
    with latest_feedback_path.open("w", encoding="utf-8") as f:
        json.dump(build_feedback_template(run_id), f, ensure_ascii=False, indent=2)
    cli.ok("Feedback", f"Saved reviewer feedback template to {feedback_path}")

    trace_path = runs_dir / f"{run_id}_trace.log"
    cli.save(trace_path)
    latest_trace_path = output_dir / "run_trace.log"
    cli.save(latest_trace_path)
    cli.ok("Trace/Log", f"Saved detailed CLI trace log to {trace_path}")

    cli.stage("Terminal Output", "Printing trend object summary")
    for trend in trend_objects:
        print(
            f"- {trend['trend_id']} | {trend['label']} | conf={trend['confidence']} | "
            f"source={trend['labeling_source']} | posts={trend['metrics']['post_count']} | "
            f"eng={trend['metrics']['total_engagement']}"
        )

    if print_json:
        cli.stage("Terminal Output", "Printing full trend_objects.json payload")
        print(json.dumps(result, ensure_ascii=False, indent=2))

    # ── Supabase sync (only runs if SUPABASE_PASSWORD is set in .env) ──
    try:
        from supabase_writer import write_trend_objects, write_run_log
        from supabase_client import is_configured
        if is_configured():
            cli.stage("Supabase", "Syncing run log + trend objects to Supabase")
            write_run_log({**result, "brand": config.get("brand", "ALL"),
                           "category": config.get("category", ""),
                           "time_window": config.get("time_window", {}),
                           "keywords_scraped": []})
            write_trend_objects(run_id, trend_objects)
            cli.ok("Supabase", "Sync complete")
        else:
            cli.info("Supabase", "Skipped (SUPABASE_PASSWORD not set)")
    except Exception as _db_err:
        cli.warn("Supabase", f"Sync skipped: {_db_err}")

    return trend_output_path, run_log_path, feedback_path, trace_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build evidence-backed XHS trend objects locally.")
    parser.add_argument("--posts", default=DEFAULT_POSTS_PATH, help="Path to XHS posts JSON")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Path to run config JSON")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory for outputs")
    parser.add_argument("--no-pretty", action="store_true", help="Disable styled CLI output")
    parser.add_argument("--print-json", action="store_true", help="Print full output JSON in terminal")
    parser.add_argument("--llm-test", action="store_true", help="Run a live LLM connectivity test")
    parser.add_argument("--live", action="store_true", help="Demo mode: keep each stage spinner visible briefly")
    args = parser.parse_args()

    trend_path, log_path, feedback_path, trace_path = run(
        posts_path=Path(args.posts),
        config_path=Path(args.config),
        output_dir=Path(args.output_dir),
        pretty=not args.no_pretty,
        print_json=args.print_json,
        llm_test=args.llm_test,
        live_mode=args.live,
    )

    print("\nXHS Trend Object Builder completed.")
    print(f"- trend objects: {trend_path}")
    print(f"- run log: {log_path}")
    print(f"- feedback template: {feedback_path}")
    print(f"- detailed trace log: {trace_path}")


if __name__ == "__main__":
    main()
