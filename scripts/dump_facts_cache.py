"""
把 WATCHLIST 每只标的的机械事实(signal_facts.build_facts)落地进 repo 的
facts_cache/<code>.json，供 Cowork（云端，连不到本机moomoo/DB）读——不用等
signals.md，也能在跟Nick聊某只票时引用当天的机械数字。

跟 signal_facts.py 的关系：signal_facts.py 是给 headless agent当场调用的CLI
(一次一只)，这个脚本是确定性地把全部WATCHLIST批量落盘，run_signals.sh里跑，
不经过LLM。

用法: .venv/bin/python scripts/dump_facts_cache.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import WATCHLIST  # noqa: E402
from signal_facts import build_facts  # noqa: E402


def main():
    project_dir = Path(__file__).resolve().parent.parent
    positions_path = project_dir / "positions.json"
    positions = json.loads(positions_path.read_text(encoding="utf-8")) if positions_path.exists() else {}

    out_dir = project_dir / "facts_cache"
    out_dir.mkdir(exist_ok=True)

    for code in WATCHLIST:
        facts = build_facts(code, positions)
        out_path = out_dir / f"{code}.json"
        out_path.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[facts_cache] {code} -> {out_path}")


if __name__ == "__main__":
    main()
