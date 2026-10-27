# Veriface (standalone)

Identity verification video tool: upload a front-facing portrait → get a **12s 720p MP4** of the same person looking **left**, then **right** — a KYC-friendly proof-of-life clip.

This is a **standalone** recreation of the Emergent preview at `gaze-verification.preview.emergentagent.com`. It does **not** depend on Emergent hosting, `emergent.sh` scripts, or Emergent LLM keys.

## Stack

| Layer | Tech |
| --- | --- |
| Frontend | React + Vite + Tailwind v4 |
| Backend | FastAPI (`/api/verify/*`) |
| Default render | Local **mock** provider (Pillow + ffmpeg) |
| Optional AI | OpenAI Videos API (`sora-2` / `sora-2-pro`) via `VIDEO_PROVIDER=openai` |

> **Note:** OpenAI shut down the public Sora Videos API on **2026-09-24**. The OpenAI provider remains for compatible proxies (`OPENAI_BASE_URL`) or any account that still exposes `/v1/videos`. Out of the box, Veriface uses the **mock** provider so the full upload → poll → download flow works offline.

## Quick start

### Prerequisites

- Node 20+
- Python 3.11+
- [ffmpeg](https://ffmpeg.org/) on `PATH` (required for mock renders)

### 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # optional
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API root: [http://127.0.0.1:8000/api/](http://127.0.0.1:8000/api/)

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

App: [http://127.0.0.1:5173](http://127.0.0.1:5173) — Vite proxies `/api` → the backend.

## API (same contract as the Emergent app)

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/verify/start` | `multipart/form-data`: `image` + `model` (`sora-2` \| `sora-2-pro`) → `{ job_id }` |
| `GET` | `/api/verify/status/{job_id}` | `{ status, message, progress, error? }` |
| `GET` | `/api/verify/download/{job_id}` | MP4 bytes when `status === completed` |

## Environment

| Variable | Default | Meaning |
| --- | --- | --- |
| `VIDEO_PROVIDER` | `mock` | `mock` or `openai` |
| `OPENAI_API_KEY` | — | Required for `openai` |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Override for proxies |
| `CORS_ORIGINS` | localhost Vite ports | Comma-separated origins |
| `VITE_API_URL` | `/api` | Frontend API base (leave default with Vite proxy) |

### Using OpenAI / a Sora-compatible proxy

```bash
# backend/.env
VIDEO_PROVIDER=openai
OPENAI_API_KEY=sk-...
# OPENAI_BASE_URL=https://your-compatible-proxy/v1
```

## Project layout

```
veriface/
  backend/app/          # FastAPI + providers (mock, openai)
  frontend/src/         # Veriface UI
  .env.example
```

## Privacy

Uploads are written under `backend/data/jobs/<id>/` for the job lifetime only and are purged after ~1 hour. Nothing is sent to Emergent. With `VIDEO_PROVIDER=mock`, nothing leaves your machine.

## License

MIT — use freely for your own deployments.
