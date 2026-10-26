"""Re-run PlainLetter's deterministic checks on saved model answers (no model call).

Use after changing the checks in core.py: the model's raw answer is kept as-is,
only checks and the Markdown report are recomputed.
    python scripts/recheck.py outputs/*.json
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from plainletter import core  # noqa: E402

for path in map(Path, sys.argv[1:]):
    data = json.loads(path.read_text(encoding="utf-8"))
    if "result" not in data:
        continue
    stem = re.sub(r"\.(es|zh)$", "", path.stem)
    letter = (ROOT / "samples" / f"{stem}.txt").read_text(encoding="utf-8").strip()
    data["checks"] = core.check(letter, data["result"], data.get("language", "en"))
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    path.with_suffix(".md").write_text(core.to_markdown(data), encoding="utf-8")
    print("rechecked", path.name)
