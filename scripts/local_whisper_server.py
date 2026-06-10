#!/usr/bin/env python3
"""Optional companion: a tiny local Whisper server for LogosForge LAN voice mode.

Run this **manually** on the machine that has the GPU/model (it is never started
by the app). It serves:

* ``GET  /health``                    → ``{"status": "ok", "model_loaded": ...}``
* ``POST /inference``                 → transcribe an uploaded WAV (whisper.cpp-style)
* ``POST /v1/audio/transcriptions``   → same handler (OpenAI-compatible path)

Both POST endpoints accept multipart/form-data with a ``file`` field (WAV) and
optional ``language``; they respond ``{"text": "..."}``.

Local-first rules:
* Binds to **127.0.0.1 by default**. Pass ``--host 0.0.0.0`` (or a LAN IP) to
  serve other machines on your **trusted local network** — keep it inside the
  LAN and behind your firewall; do **not** expose it to the public internet.
* Requires a **local** faster-whisper model path (``--model``) — this script
  never downloads models.
* Optional static token: start with ``--token SECRET`` and configure the same
  value in LogosForge (header ``X-Voice-Token``). The token is never logged.

Example:
    pip install faster-whisper
    python scripts/local_whisper_server.py --model /models/faster-whisper-small \\
        --host 192.168.1.50 --port 8000
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN_HEADER = "X-Voice-Token"

_model = None
_model_path = ""
_token = ""


def _load_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel  # local path only — no download
        _model = WhisperModel(_model_path, device="auto", compute_type="int8")
    return _model


def _extract_wav(body: bytes, content_type: str) -> tuple[bytes, str]:
    """Pull the ``file`` part (and optional ``language``) out of a multipart
    body. Falls back to treating the whole body as WAV for raw uploads."""
    match = re.search(r'boundary="?([^";,]+)"?', content_type or "")
    if not match:
        return (body, "")
    boundary = ("--" + match.group(1)).encode()
    wav, language = b"", ""
    for part in body.split(boundary):
        header, _, payload = part.partition(b"\r\n\r\n")
        if not payload:
            continue
        payload = payload.rstrip(b"\r\n-")
        if b'name="file"' in header:
            wav = payload
        elif b'name="language"' in header:
            language = payload.decode("utf-8", "replace").strip()
    return (wav, language)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        return not _token or self.headers.get(TOKEN_HEADER, "") == _token

    def do_GET(self):  # noqa: N802 (http.server signature)
        if self.path.rstrip("/") in ("", "/health".rstrip("/"), "/health"):
            self._send(200, {"status": "ok", "model_loaded": _model is not None})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        if self.path not in ("/inference", "/v1/audio/transcriptions"):
            self._send(404, {"error": "not found"})
            return
        if not self._authorized():
            self._send(401, {"error": "missing or wrong token"})
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length) if length else b""
        wav, language = _extract_wav(body, self.headers.get("Content-Type", ""))
        if not wav:
            self._send(400, {"error": "no audio file"})
            return
        try:
            model = _load_model()
            segments, _info = model.transcribe(
                io.BytesIO(wav), language=(language or None))
            text = " ".join(s.text.strip() for s in segments).strip()
            self._send(200, {"text": text})
        except Exception as exc:  # report, never crash the server loop
            self._send(500, {"error": f"transcription failed: {exc}"})

    def log_message(self, fmt, *args):  # quiet-ish log; never logs tokens/audio
        sys.stderr.write("[local-whisper] %s\n" % (fmt % args))


def main() -> int:
    global _model_path, _token
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True,
                        help="LOCAL faster-whisper model directory (no downloads)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Bind address (default 127.0.0.1; use a LAN IP or "
                             "0.0.0.0 only inside a trusted local network)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--token", default="",
                        help=f"Optional static token (header {TOKEN_HEADER})")
    args = parser.parse_args()
    _model_path = args.model
    _token = args.token

    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        print("faster-whisper is not installed: pip install faster-whisper",
              file=sys.stderr)
        return 2

    print(f"Local Whisper server on http://{args.host}:{args.port} "
          f"(model: {args.model}). Keep this inside your trusted LAN.")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
