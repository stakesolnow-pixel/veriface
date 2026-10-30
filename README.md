# Veriface (standalone) — webcam liveness

Free KYC-style **proof of life**: record yourself looking **left**, then **right** on your webcam.

No Sora, no fal.ai, no Replicate, no ffmpeg fake pan. Works on a **GTX 960** because it doesn’t need a GPU model.

## Why webcam?

| Approach | Cost | Realistic? | On GTX 960 |
| --- | --- | --- | --- |
| ffmpeg slide still | free | no | yes |
| fal / Replicate I2V | paid | better | n/a |
| Local face-swap / LivePortrait | free | maybe | usually too little VRAM |
| **Webcam head-turn** | **free** | **yes** | **yes** |

Claude **cannot** generate or face-swap video. Optional: set `ANTHROPIC_API_KEY` so Claude can **review** stills from your recording (PASS / WEAK / FAIL).

## Quick start (Windows)

### Backend

```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Frontend

```bat
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173 → **Enable camera** → follow LEFT / RIGHT cues → **Download clip**.

Use **Chrome or Edge**. Allow camera permission.

### Optional Claude review

In `backend\.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...
```

Restart uvicorn, record a clip, click **Optional: Claude review**.

## API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/` | Health |
| `POST` | `/api/verify/webcam-review` | Optional Claude review (`frames` image uploads) |

Legacy image→video routes (`/api/verify/start|status|download`) still exist if you configure a paid provider later.

## License

MIT
