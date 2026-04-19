"""
atypica_client.py — Atypica API client for dynamic brand profile and persona generation.

Protocol: JSON-RPC 2.0 over POST https://atypica.ai/mcp/study
Auth:     Authorization: Bearer <ATYPICA_API_KEY>   (key format: atypica_xxx)

Workflow for each query:
  1. atypica_study_create   — open a research session, get study_id
  2. atypica_study_send_message — submit the research question
  3. atypica_study_get_messages — poll until the AI marks the study complete
  4. atypica_study_get_report   — retrieve the final report text

Each HTTP call has a 120-second timeout (AI execution takes 10–120 seconds).

Falls back gracefully to existing static JSON if:
  - ATYPICA_API_KEY is not set
  - Any API call fails or times out
  - LLM structuring fails

Usage:
    from atypica_client import get_or_refresh_brand_data
    brand_profile = get_or_refresh_brand_data("Tiffany")
    brand_profile = get_or_refresh_brand_data("Tiffany", force_refresh=True)
"""

import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# ── Config ──────────────────────────────────────────────────────────────────────
ATYPICA_MCP_URL    = "https://atypica.ai/mcp/study"
CACHE_MAX_AGE_DAYS = 7
MSG_TIMEOUT_SEC    = 120   # per HTTP call — AI takes 10–120 s
POLL_INTERVAL_SEC  = 5     # seconds between get_messages polls
POLL_MAX_ATTEMPTS  = 36    # 36 × 5 s = 3 minutes max poll per study
BASE_DIR = Path(__file__).parent


# ── Slug helpers ─────────────────────────────────────────────────────────────────

def _brand_slug(brand_name: str) -> str:
    """Convert brand name to lowercase filesystem slug. e.g. 'Tiffany & Co.' → 'tiffany'"""
    return (
        brand_name.lower()
        .strip()
        .split("&")[0]
        .strip()
        .replace(" ", "_")
        .replace(".", "")
        .replace(",", "")
        .rstrip("_")
    )


def _profile_path(brand_name: str) -> Path:
    return BASE_DIR / f"brand_profile_{_brand_slug(brand_name)}.json"


# ── Cache helpers ────────────────────────────────────────────────────────────────

def _is_cache_fresh(brand_name: str) -> bool:
    """Return True if the cached profile file exists and is younger than CACHE_MAX_AGE_DAYS."""
    path = _profile_path(brand_name)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cached_at_str = data.get("_cached_at")
        if not cached_at_str:
            return False
        cached_at = datetime.fromisoformat(cached_at_str)
        age = datetime.now(timezone.utc) - cached_at.replace(tzinfo=timezone.utc)
        return age < timedelta(days=CACHE_MAX_AGE_DAYS)
    except Exception:
        return False


def _load_static(brand_name: str) -> Optional[dict]:
    """Load static brand profile JSON, strip internal _* keys before returning."""
    path = _profile_path(brand_name)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("_cached_at", None)
        return data
    except Exception:
        return None


# ── JSON-RPC 2.0 core ────────────────────────────────────────────────────────────

def _get_atypica_key() -> str:
    return os.environ.get("ATYPICA_API_KEY", "")


def _mcp_call(tool_name: str, arguments: dict, api_key: str, request_id: int = 1) -> dict:
    """
    Make one JSON-RPC 2.0 call to the Atypica MCP endpoint.

    Returns the 'result' payload on success.
    Raises RuntimeError on JSON-RPC error, requests.HTTPError on HTTP failure.
    """
    try:
        import requests
    except ImportError:
        raise ImportError("requests package required — run: pip install requests")

    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
        "id": request_id,
    }
    resp = requests.post(
        ATYPICA_MCP_URL,
        json=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=MSG_TIMEOUT_SEC,
    )
    resp.raise_for_status()
    data = resp.json()

    # JSON-RPC error object
    if "error" in data:
        raise RuntimeError(
            f"Atypica MCP error for '{tool_name}': {data['error']}"
        )

    return data.get("result", data)


# ── MCP workflow helpers ─────────────────────────────────────────────────────────

def _extract_study_id(result: dict) -> str:
    """Pull study_id from any response shape the API might return."""
    for key in ("study_id", "studyId", "id", "session_id", "sessionId"):
        val = result.get(key)
        if val:
            return str(val)
    # Some APIs nest it one level deep
    for key in ("data", "result", "study"):
        nested = result.get(key)
        if isinstance(nested, dict):
            for ikey in ("study_id", "studyId", "id"):
                val = nested.get(ikey)
                if val:
                    return str(val)
    raise ValueError(f"Could not extract study_id from response: {result}")


def _is_study_complete(messages_result: dict) -> bool:
    """
    Inspect the get_messages result and decide whether the study is done.
    Looks for common completion signals across possible response shapes.
    """
    # Top-level status field
    status = str(messages_result.get("status", "")).lower()
    if status in ("complete", "completed", "done", "finished", "success"):
        return True

    # Check inside a nested 'study' object
    study = messages_result.get("study") or {}
    if isinstance(study, dict):
        s = str(study.get("status", "")).lower()
        if s in ("complete", "completed", "done", "finished", "success"):
            return True

    # Some APIs signal completion via the last message role
    messages = messages_result.get("messages") or []
    if isinstance(messages, list) and messages:
        last = messages[-1]
        if isinstance(last, dict):
            role = str(last.get("role", "")).lower()
            msg_status = str(last.get("status", "")).lower()
            if role in ("assistant", "agent", "report") or msg_status in ("complete", "done"):
                return True

    # Boolean 'completed' field
    if messages_result.get("completed") is True:
        return True

    return False


def _extract_report_text(report_result: dict) -> str:
    """Pull report text from the get_report result, trying common field names."""
    for key in ("report", "content", "text", "result", "output", "body"):
        val = report_result.get(key)
        if val and isinstance(val, str):
            return val

    # Nested under 'data'
    data = report_result.get("data")
    if isinstance(data, dict):
        for key in ("report", "content", "text", "result"):
            val = data.get(key)
            if val and isinstance(val, str):
                return val

    # Last resort: stringify the whole result
    return json.dumps(report_result, ensure_ascii=False)


# ── Main study workflow ──────────────────────────────────────────────────────────

def _call_atypica(query: str) -> str:
    """
    Full MCP workflow for one research query:
      1. atypica_study_create   → study_id
      2. atypica_study_send_message → trigger AI research
      3. atypica_study_get_messages → poll until complete
      4. atypica_study_get_report  → return report text

    Raises on unrecoverable failure so callers can fall back to cached data.
    """
    api_key = _get_atypica_key()
    if not api_key:
        raise EnvironmentError("ATYPICA_API_KEY not set")

    # ── Step 1: Create study session ────────────────────────────────────────────
    print("  [Atypica] Step 1 — creating study session...")
    create_result = _mcp_call(
        "atypica_study_create",
        {"content": query},
        api_key,
        request_id=1,
    )
    study_id = _extract_study_id(create_result)
    print(f"  [Atypica] Study ID: {study_id}")

    # ── Step 2: Send message to drive research ───────────────────────────────────
    print("  [Atypica] Step 2 — sending research message...")
    _mcp_call(
        "atypica_study_send_message",
        {"study_id": study_id, "content": query},
        api_key,
        request_id=2,
    )

    # ── Step 3: Poll for completion ──────────────────────────────────────────────
    print("  [Atypica] Step 3 — polling for completion (up to "
          f"{POLL_MAX_ATTEMPTS * POLL_INTERVAL_SEC}s)...")
    for attempt in range(1, POLL_MAX_ATTEMPTS + 1):
        time.sleep(POLL_INTERVAL_SEC)
        messages_result = _mcp_call(
            "atypica_study_get_messages",
            {"study_id": study_id},
            api_key,
            request_id=3,
        )
        if _is_study_complete(messages_result):
            elapsed = attempt * POLL_INTERVAL_SEC
            print(f"  [Atypica] Study complete after {elapsed}s")
            break
        if attempt % 6 == 0:
            elapsed = attempt * POLL_INTERVAL_SEC
            print(f"  [Atypica] Still running... ({elapsed}s elapsed)")
    else:
        raise TimeoutError(
            f"Atypica study {study_id} did not complete within "
            f"{POLL_MAX_ATTEMPTS * POLL_INTERVAL_SEC} seconds"
        )

    # ── Step 4: Retrieve final report ────────────────────────────────────────────
    print("  [Atypica] Step 4 — retrieving report...")
    report_result = _mcp_call(
        "atypica_study_get_report",
        {"study_id": study_id},
        api_key,
        request_id=4,
    )
    report_text = _extract_report_text(report_result)
    print(f"  [Atypica] Report received ({len(report_text)} chars)")
    return report_text


# ── LLM-based JSON structuring ───────────────────────────────────────────────────

_SCHEMA_HINT = """
{
  "brand_name": "string",
  "brand_name_cn": "Chinese brand name",
  "current_creative_director": "string",
  "aesthetic_dna": "1-2 sentence description",
  "current_direction": "1-2 sentence description of current strategy",
  "brand_voice": "adjectives describing brand tone",
  "active_categories": ["list of product category strings"],
  "client_archetypes": [
    {
      "name": "Chinese + pinyin name",
      "age_range": "XX-XX",
      "lifestyle": "string",
      "aspiration": "string",
      "occupation": "string",
      "typical_budget_rmb": number,
      "entry_budget_rmb": number,
      "stretch_budget_rmb": number,
      "trend_language_that_resonates": "string",
      "what_they_would_never_buy": "string",
      "purchase_motivations": ["list"],
      "occasion_triggers": ["list"],
      "preferred_collections": ["list"]
    }
  ],
  "hero_products": {
    "collection_name": ["Product Name (¥price range)"]
  },
  "budget_tiers": {
    "entry": {"range_rmb": "¥X-Y", "products": [], "ca_angle": "string"},
    "core": {"range_rmb": "¥X-Y", "products": [], "ca_angle": "string"},
    "aspirational": {"range_rmb": "¥X-Y", "products": [], "ca_angle": "string"},
    "investment": {"range_rmb": "¥X+", "products": [], "ca_angle": "string"}
  },
  "aesthetic_pillars": [
    {"name": "string", "description": "one sentence"}
  ],
  "competitive_differentiation": {
    "competitor_brand": "how brand differs from this competitor"
  },
  "brand_taboos": {
    "category_taboos": ["keyword list"]
  }
}
"""


def _structure_with_llm(brand_name: str, profile_text: str, personas_text: str) -> dict:
    """
    Call OpenRouter LLM to parse raw Atypica text into structured brand profile JSON.
    Returns empty dict on any failure (caller will merge with static fallback).
    """
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not openrouter_key:
        print("  [Atypica] OPENROUTER_API_KEY not set — cannot structure response")
        return {}

    try:
        from openai import OpenAI
    except ImportError:
        print("  [Atypica] openai package not installed — cannot structure response")
        return {}

    client = OpenAI(api_key=openrouter_key, base_url="https://openrouter.ai/api/v1")
    model = os.environ.get("DEFAULT_MODEL", "anthropic/claude-3-5-sonnet")

    profile_excerpt = profile_text[:6000]
    personas_excerpt = personas_text[:6000]

    prompt = f"""You are extracting structured brand data from research reports about {brand_name} for a luxury retail AI agent.

BRAND PROFILE REPORT (from Atypica):
{profile_excerpt}

CONSUMER PERSONAS REPORT (from Atypica):
{personas_excerpt}

Extract this information into a valid JSON object matching this schema exactly:
{_SCHEMA_HINT}

Rules:
- Include ALL consumer personas found in the report — do not cap or limit
- Use Chinese + pinyin format for persona names where applicable
- Price ranges should be in RMB (¥)
- active_categories should include "luxury_jewelry" for jewelry brands
- Return ONLY the JSON object, no markdown, no explanation

JSON:"""

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()
        parsed = json.loads(raw)
        print(f"  [Atypica] Structured {len(parsed.get('client_archetypes', []))} archetypes from LLM")
        return parsed
    except Exception as e:
        print(f"  [Atypica] LLM structuring failed: {e}")
        return {}


# ── Public API ───────────────────────────────────────────────────────────────────

def get_brand_profile(brand_name: str) -> str:
    """
    Call Atypica to research brand positioning, hero products, and voice.
    Returns raw report text.
    """
    query = (
        f"What is {brand_name}'s current aesthetic positioning, hero products with price ranges "
        f"in RMB, key collections, competitive differentiation vs other luxury brands, brand taboos, "
        f"and brand voice for the Chinese luxury market in 2026?"
    )
    return _call_atypica(query)


def get_consumer_personas(brand_name: str) -> str:
    """
    Call Atypica to generate all consumer personas for the brand in China.
    Returns raw report text.
    """
    query = (
        f"Generate ALL relevant consumer personas for {brand_name} customers in China's luxury market. "
        f"Do not limit the number — include every distinct consumer segment that meaningfully interacts "
        f"with this brand across China. For each persona include: name, age range, lifestyle, occupation, "
        f"typical budget in RMB, entry budget, typical budget, stretch budget, purchase motivations, "
        f"occasion triggers, XHS behavior, what content resonates, what they value in a CA interaction, "
        f"aesthetic preferences, which specific collections they prefer, competitor brands they consider, "
        f"and what makes them choose {brand_name}."
    )
    return _call_atypica(query)


def get_or_refresh_brand_data(brand_name: str, force_refresh: bool = False) -> dict:
    """
    Return a complete brand profile dict for brand_name.

    Cache logic:
      - If cached file exists and is < 7 days old AND force_refresh=False: return cached.
      - Otherwise: call Atypica for brand profile + consumer personas, structure with LLM,
        merge with static fallback JSON, save to brand_profile_{slug}.json with timestamp.

    Fallback:
      - If ATYPICA_API_KEY not set or any API/LLM step fails:
        loads and returns existing static JSON and prints a warning.
    """
    path = _profile_path(brand_name)

    # Return fresh cache if available
    if not force_refresh and _is_cache_fresh(brand_name):
        print(f"[Atypica] Using cached brand profile for {brand_name} ({path.name})")
        return _load_static(brand_name) or {}

    # No key → fall back immediately
    api_key = _get_atypica_key()
    if not api_key:
        print(f"[Atypica] ATYPICA_API_KEY not set — using cached brand profile for {brand_name}")
        static = _load_static(brand_name)
        if static:
            return static
        raise FileNotFoundError(
            f"No cached brand profile found at {path} and ATYPICA_API_KEY is not set. "
            f"Create {path} manually or set ATYPICA_API_KEY."
        )

    print(f"\n[Atypica] Refreshing brand data for {brand_name}...")
    profile_text = ""
    personas_text = ""

    try:
        print("[Atypica] Step 1/2 — fetching brand profile...")
        profile_text = get_brand_profile(brand_name)
    except Exception as e:
        print(f"[Atypica] Brand profile fetch failed: {e}")

    try:
        print("[Atypica] Step 2/2 — fetching consumer personas...")
        personas_text = get_consumer_personas(brand_name)
    except Exception as e:
        print(f"[Atypica] Consumer personas fetch failed: {e}")

    if not profile_text and not personas_text:
        print(f"[Atypica] Both API calls failed — using cached brand profile for {brand_name}")
        static = _load_static(brand_name)
        if static:
            return static
        raise RuntimeError(f"Atypica API unavailable and no cached profile found for {brand_name}")

    # Structure the text into JSON with LLM
    structured = _structure_with_llm(brand_name, profile_text, personas_text)

    # Merge: static fallback provides defaults; structured overrides where present
    base = _load_static(brand_name) or {}
    merged = {**base, **{k: v for k, v in structured.items() if v}}

    # Ensure required fields
    merged.setdefault("brand_name", brand_name)
    merged.setdefault("active_categories", ["luxury_jewelry", "luxury_fashion"])

    # Store raw Atypica text and metadata
    merged["_atypica_profile_raw"] = profile_text[:2000] if profile_text else ""
    merged["_atypica_personas_raw"] = personas_text[:2000] if personas_text else ""
    merged["_cached_at"] = datetime.now(timezone.utc).isoformat()
    merged["_source"] = "atypica_api"

    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Atypica] Brand profile saved → {path}")

    # Return clean version (strip internal _* keys)
    clean = {k: v for k, v in merged.items() if not k.startswith("_")}
    return clean
