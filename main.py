import os
import sys
import subprocess
from config import ANTHROPIC_API_KEY, OPENROUTER_API_KEY, DEFAULT_MODEL, BRAND

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


def run_module(module_dir, script_name, *args):
    print(f"\n{'='*60}")
    print(f"Running {module_dir}/{script_name}")
    print(f"{'='*60}")
    workdir = os.path.join(REPO_ROOT, module_dir)
    script_path = os.path.join(workdir, script_name)
    if not os.path.exists(script_path):
        print(f"Script {script_path} not found. Skipping.")
        return False

    env = os.environ.copy()
    if ANTHROPIC_API_KEY:
        env["ANTHROPIC_API_KEY"] = ANTHROPIC_API_KEY
    if OPENROUTER_API_KEY:
        env["OPENROUTER_API_KEY"] = OPENROUTER_API_KEY
        env["OPENAI_API_KEY"] = OPENROUTER_API_KEY
    env["DEFAULT_MODEL"] = DEFAULT_MODEL
    env["BRAND"] = BRAND

    try:
        result = subprocess.run(
            [sys.executable, script_path, *args],
            cwd=workdir,
            env=env,
            check=True
        )
        print(f"✓ Finished {module_dir}/{script_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Error in {module_dir}/{script_name}: {e}")
        return False


def main():
    print("=" * 60)
    print(f"  Agent Pipeline — Brand: {BRAND}")
    print(f"  Model: {DEFAULT_MODEL}")
    print("=" * 60)

    # Module 1 — XHS scraper + trend object builder
    run_module("module_1", "xhs_trend_builder.py")

    # Module 2 — Trend relevance & materiality filter
    run_module("module_2", "agent.py")

    # Module 3 — CA trend brief generator
    run_module(
        "module_3/trend_brief_agent",
        "agent.py",
        "--brand",
        BRAND,
        "--city",
        "Shanghai",
    )

    # Module 4 — Client memory structurer
    run_module("module_4", "First_Run.py")

    # Module 5 — Outreach angle agent
    run_module("module_5", "agent.py")

    print("\n" + "=" * 60)
    print("  Pipeline complete: Modules 1 → 2 → 3 → 4 → 5")
    print("=" * 60)


if __name__ == "__main__":
    main()
