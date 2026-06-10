# Local LAN Whisper Server (voice MVP — LAN mode)

LAN mode lets LogosForge use **another machine on your trusted local network**
(e.g. a workstation with an RTX GPU) as the Whisper transcription server.
Microphone capture and buffering stay **on your computer**; only finalized audio
segments are uploaded to the server **you** configured.

> **LAN mode sends audio only to the configured local network Whisper server.
> Do not use public URLs.** Public IPs/domains, ngrok and cloud-tunnel URLs are
> **blocked** in this Alpha build (`voice_lan_allow_only_private_hosts` is on by
> default and there is no public-URL override). Redirects are refused. Hostnames
> are never DNS-resolved, so a public domain cannot smuggle in a "private" IP.

Allowed addresses: `localhost` / `127.0.0.1` / `::1`, RFC1918 ranges
(`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), IPv4 link-local
(`169.254.0.0/16`) and `.local` mDNS names.

## LogosForge settings (LAN mode)

| key | meaning | default |
|-----|---------|---------|
| `voice_backend_mode` | `"lan_server"` | `"disabled"` |
| `voice_lan_base_url` | e.g. `http://192.168.1.50:8000` | `""` |
| `voice_lan_api_type` | `openai_compatible` · `whisper_cpp` · `custom` | `openai_compatible` |
| `voice_lan_transcription_endpoint` | custom api_type only | `""` |
| `voice_lan_health_endpoint` | health probe path | `/health` |
| `voice_lan_timeout_seconds` | request timeout | `60` |
| `voice_lan_auth_header_name` / `voice_lan_auth_token` | optional static local token (never logged) | `""` |
| `voice_lan_max_audio_seconds` / `voice_lan_max_payload_mb` | refuse oversize segments before sending | `60` / `25` |

Endpoint per api_type: `openai_compatible` → `POST {base}/v1/audio/transcriptions`,
`whisper_cpp` → `POST {base}/inference`, `custom` → your configured path. The
request is `multipart/form-data` with a `file` field (WAV, 16 kHz mono) and an
optional `language` field; the response is JSON `{"text": "..."}` or plain text.

## Option A — companion script (faster-whisper)

A tiny stdlib HTTP server ships at `scripts/local_whisper_server.py`. It is
**never started by the app** — run it yourself on the server machine:

```bash
pip install faster-whisper
python scripts/local_whisper_server.py \
    --model /models/faster-whisper-small \
    --host 192.168.1.50 --port 8000          # 127.0.0.1 by default
```

- `--model` must be a **local** model directory — the script never downloads.
- It binds `127.0.0.1` by default; pass a LAN IP (or `0.0.0.0`) **only inside a
  trusted LAN**, with your firewall allowing the chosen port. Never expose it to
  the public internet.
- Optional `--token SECRET` → configure the same value in LogosForge
  (`voice_lan_auth_header_name = "X-Voice-Token"`, `voice_lan_auth_token`).
- Serves `GET /health` plus both transcription paths above.

## Option B — whisper.cpp server

```bash
./server -m /models/ggml-base.en.bin --host 192.168.1.50 --port 8081
```

- Set `voice_lan_api_type = "whisper_cpp"` (endpoint `/inference`).
- Same rules: bind to the LAN interface intentionally, firewall the port, keep
  it inside the trusted LAN.

Any other OpenAI-compatible local Whisper server works with
`openai_compatible`; anything else can be wired with `custom` + your endpoint.

## Troubleshooting

- **"Local LAN Whisper server is not reachable."** — server not running /
  wrong port / firewall. Use the panel's **Check LAN server** button.
- **"LAN Whisper server must be a trusted local network address…"** — the URL
  is public or not parseable as a private address; use a private LAN IP,
  `localhost`, or a `.local` name.
- **HTTP 401** — token mismatch between the server and LogosForge.
