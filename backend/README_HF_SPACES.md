# Deploy Pulse Backend on Hugging Face Spaces (Docker)

This guide deploys the backend from this `backend/` folder to Hugging Face Spaces without any Render dependency.

## 1) Create the Space

1. Open Hugging Face and click **Create new Space**.
2. Select your account/org and set a Space name (example: `pulse-ai-backend`).
3. Set **SDK** to **Docker**.
4. Choose visibility (Public or Private).
5. Click **Create Space**.

## 2) Choose one deployment layout

### Option A (recommended): connect this whole repository to the Space

This repository now includes a **root-level** `Dockerfile` and `README.md` configured for Hugging Face Docker Spaces.

- In Hugging Face, connect/push this repository as-is.
- The root Docker image automatically runs backend app from `backend/main.py`.
- No folder reshuffling needed.

### Option B: push only backend folder contents to the Space root

If you prefer a backend-only Space repo, your Space root should contain files like:

- `main.py`
- `requirements.txt`
- `Dockerfile`
- `config/`, `routers/`, `services/`, `middleware/`, `models/`, `knowledge/`, `dependencies/`

Important for both options:

- Do not push `.venv`, `.env`, or `__pycache__`.
- Keep Space SDK set to `docker`.

## 3) Add Space metadata in README.md

In the Space repo root, ensure `README.md` starts with:

```yaml
---
title: Pulse AI Backend
emoji: 🩺
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---
```

After this YAML block, you can add any normal README content.

## 4) Configure Variables and Secrets in Space Settings

Open **Space -> Settings -> Variables and secrets** and add:

### Secrets

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `JWT_SECRET`
- `GROQ_API_KEY` (optional but recommended)

### Variables

- `APP_ENV=production`
- `DEBUG=false`
- `APP_NAME=Pulse API`
- `SUPABASE_STORAGE_BUCKET=medical-records`
- `CORS_ORIGINS=*`

## 5) Deploy

1. Push changes to your Space repository.
2. Open the **Build logs** tab and wait for success.
3. Test:
   - `https://<your-space>.hf.space/`
   - `https://<your-space>.hf.space/api/v1/health`

## 6) Validate the Space directly

1. Open `https://<your-space>.hf.space/`.
2. Check `https://<your-space>.hf.space/api/v1/health`.
3. If you use the bundled frontend shell, it should call `https://<your-space>.hf.space/api/v1/...` by default.
4. Confirm no CORS errors in browser console.

## Notes for free tier

- Free Space can sleep when idle (cold starts are expected).
- First request after sleep may take longer.
- Heavy ML requests may be slower on free CPU hardware.

If free-tier performance is not enough, keep this same Docker setup and move to paid hardware tier or another host without changing backend code.