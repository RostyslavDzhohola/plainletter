"""Run Spark-X2.6-4B on every sample letter and save real outputs + run metadata.

    python scripts/run_samples.py            # English
    python scripts/run_samples.py --lang es  # also try Spanish
"""
import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from plainletter import core  # noqa: E402


def hardware() -> dict:
    def sh(*cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:  # noqa: BLE001
            return None
    mem = sh("sysctl", "-n", "hw.memsize")
    return {
        "machine": platform.machine(),
        "cpu": sh("sysctl", "-n", "machdep.cpu.brand_string") or platform.processor(),
        "memory_gb": round(int(mem) / 2**30) if mem and mem.isdigit() else None,
        "os": f"{platform.system()} {platform.mac_ver()[0] or platform.release()}",
        "python": platform.python_version(),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="en")
    ap.add_argument("--only", help="substring of a sample name")
    a = ap.parse_args()
    out = ROOT / "outputs"
    out.mkdir(exist_ok=True)
    run = {"hardware": hardware(), "runtime": core.model_info(), "system_prompt": core.SYSTEM_PROMPT,
           "user_template": core.USER_TEMPLATE, "json_schema": core.SCHEMA, "runs": []}
    for f in sorted((ROOT / "samples").glob("*.txt")):
        if a.only and a.only not in f.stem:
            continue
        letter = f.read_text(encoding="utf-8")
        print(f"→ {f.name} ({a.lang}) ...", flush=True)
        data = core.explain(letter, a.lang)
        suffix = "" if a.lang == "en" else f".{a.lang}"
        (out / f"{f.stem}{suffix}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        (out / f"{f.stem}{suffix}.md").write_text(core.to_markdown(data), encoding="utf-8")
        c = data["checks"]
        row = {"sample": f.name, "language": a.lang, **data["stats"],
               "summary_grade": c["summary_grade"], "letter_grade": c["letter_grade"],
               "deadlines": len(data["result"]["deadlines"]), "ungrounded_quotes": c["ungrounded_quotes"],
               "contacts": len(data["result"]["contacts"]), "ungrounded_phones": c["ungrounded_phones"],
               "dates_not_in_deadlines": [x["text"] for x in c["dates_not_in_deadlines"]]}
        run["runs"].append(row)
        print("  ", json.dumps(row))
    name = "run-metadata.json" if a.lang == "en" else f"run-metadata.{a.lang}.json"
    (out / name).write_text(json.dumps(run, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
