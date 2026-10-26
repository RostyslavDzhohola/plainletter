"""Command line: python -m plainletter letter.txt [--lang es] [--note "..."] [--json out.json]"""

from __future__ import annotations

import argparse
import json
import sys

from . import core


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["serve"]:
        s = argparse.ArgumentParser(prog="plainletter serve", description="Start the local web app.")
        s.add_argument("--port", type=int, default=8765)
        from .server import serve
        serve(s.parse_args(argv[1:]).port)
        return
    if argv[:1] == ["info"]:
        print(json.dumps(core.model_info(), indent=2))
        return

    p = argparse.ArgumentParser(
        prog="plainletter",
        description="Explain a confusing official letter in plain language (offline, Spark-X2.6-4B via Ollama).",
        epilog="Other commands: `plainletter serve [--port 8765]` starts the web app; `plainletter info` shows model info.",
    )
    p.add_argument("file", nargs="?", help="letter text file, image (with Tesseract), or - for stdin")
    p.add_argument("--lang", default="en", choices=sorted(core.LANGUAGES))
    p.add_argument("--note", default="", help="your situation, used for the reply draft")
    p.add_argument("--json", dest="json_out", help="also save full JSON (answer, checks, stats) here")
    p.add_argument("--md", dest="md_out", help="also save the Markdown report here")
    a = p.parse_args(argv)
    if not a.file:
        p.print_help()
        sys.exit(1)

    if a.file == "-":
        letter = sys.stdin.read()
    elif a.file.lower().endswith((".png", ".jpg", ".jpeg", ".heic", ".tif", ".tiff")):
        letter = core.ocr_image(a.file)
    else:
        with open(a.file, encoding="utf-8") as f:
            letter = f.read()

    print(f"Reading the letter with {core.MODEL} (local)...", file=sys.stderr)
    try:
        data = core.explain(letter, a.lang, a.note)
    except (core.ModelError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    data["letter"] = letter
    md = core.to_markdown(data)
    print(md)
    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    if a.md_out:
        with open(a.md_out, "w", encoding="utf-8") as f:
            f.write(md)
