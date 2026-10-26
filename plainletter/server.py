"""Tiny local web server. Binds to 127.0.0.1 only: letters never leave the machine."""

from __future__ import annotations

import base64
import json
import os
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import core

STATIC = Path(__file__).parent / "static"
SAMPLES = Path(__file__).resolve().parent.parent / "samples"


class Handler(BaseHTTPRequestHandler):
    timeout = 60  # seconds to wait on a slow client socket
    def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode())

    def log_message(self, fmt, *args):  # keep letter content out of logs
        print("[plainletter]", self.command, self.path.split("?")[0], args[1] if len(args) > 1 else "")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        if path == "/api/info":
            return self._json(200, core.model_info())
        if path == "/api/samples":
            items = [{"name": p.stem, "text": p.read_text(encoding="utf-8")} for p in sorted(SAMPLES.glob("*.txt"))]
            return self._json(200, items)
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._json(400, {"error": "Bad Content-Length."})
        if n < 0:
            return self._json(400, {"error": "Bad Content-Length."})
        if n > 15_000_000:
            return self._json(413, {"error": "Too large."})
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return self._json(400, {"error": "Bad request."})
        path = self.path.split("?")[0]
        try:
            if path == "/api/explain":
                data = core.explain(body.get("letter", ""), body.get("language", "en"), body.get("note", ""))
                return self._json(200, data)
            if path == "/api/ocr":
                raw = base64.b64decode(body.get("image", "").split(",")[-1])
                suffix = os.path.splitext(body.get("filename", "x.png"))[1] or ".png"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as f:
                    f.write(raw)
                    f.flush()
                    return self._json(200, {"text": core.ocr_image(f.name)})
        except ValueError as e:
            return self._json(400, {"error": str(e)})
        except core.ModelError as e:
            return self._json(502, {"error": str(e)})
        self._json(404, {"error": "not found"})


def serve(port: int = 8765) -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"PlainLetter running at http://127.0.0.1:{port}  (model: {core.MODEL}, Ollama: {core.OLLAMA_URL})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
