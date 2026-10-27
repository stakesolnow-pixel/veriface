# Veriface (standalone)

Identity verification video tool: upload a front-facing portrait → get a **~10s 720p MP4** of the same person looking **left**, then **right** — a KYC-friendly proof-of-life clip.

Standalone recreation of the Emergent preview. **No Emergent dependency.**

## How generation works

Anthropic **does not** offer a video API. Veriface’s `anthropic` provider does this instead:

1. **Claude (vision)** reads the portrait and writes a strict liveness prompt  
2. **Kling via fal.ai** turns that into an image-to-video clip (`FAL_KEY`)  
3. If `FAL_KEY` is missing, it falls back to a **local ffmpeg mock** after Claude crafts the prompt  

| `VIDEO_PROVIDER` | Needs | What it does |
| --- | --- | --- |
| `anthropic` | `ANTHROPIC_API_KEY` (+ `FAL_KEY` for real video) | Claude prompt → Kling (or mock) |
| `fal` | `FAL_KEY` | Kling only (fixed prompt) |
| `mock` | ffmpeg | Local pan demo, no cloud |
| `openai` | `OPENAI_API_KEY` | Legacy; public `/v1/videos` shut down 2026-09-24 |

## Quick start

### Prerequisites

- Node 20+
- Python 3.11–3.14
- [ffmpeg](https://ffmpeg.org/) on `PATH` (for mock). Windows: `winget install ffmpeg`
- `ANTHROPIC_API_KEY` from https://console.anthropic.com  
- `FAL_KEY` from https://fal.ai (for real AI video)

### Backend

```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

Edit `backend\.env`:

```env
VIDEO_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
FAL_KEY=your-fal-key
```

```bat
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Frontend

```bat
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173

## API

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/verify/start` | `image` + `model` (`sora-2`=Kling fast, `sora-2-pro`=Kling Pro) |
| `GET` | `/api/verify/status/{job_id}` | Job status |
| `GET` | `/api/verify/download/{job_id}` | MP4 when completed |

## Privacy

Uploads live under `backend/data/jobs/<id>/` and are purged after ~1 hour. With `mock` only, nothing leaves your machine. With `anthropic`/`fal`, the image is sent to Anthropic and/or fal.ai per their policies.

## License

MIT
