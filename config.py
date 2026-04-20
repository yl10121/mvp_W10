import os
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent
load_dotenv(_REPO_ROOT / ".env")

# 团队约定「一把钥匙」：只配 OPENROUTER_API_KEY 时，同步为 OpenAI 兼容客户端所用的变量（M1 trend builder 等）
OPENROUTER_API_KEY = (os.getenv("OPENROUTER_API_KEY") or "").strip()
if OPENROUTER_API_KEY and not (os.getenv("OPENAI_API_KEY") or "").strip():
    os.environ["OPENAI_API_KEY"] = OPENROUTER_API_KEY

# 未使用 OpenRouter 时，仍可直接连 Anthropic 官方 API
ANTHROPIC_API_KEY = (os.getenv("ANTHROPIC_API_KEY") or "").strip()

# 默认与 OpenRouter 常见用法对齐；可在 .env 覆盖
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "openai/gpt-4o-mini")
BRAND = os.getenv("BRAND", "Tiffany")
