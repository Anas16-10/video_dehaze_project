# Video Dehaze Studio

Modern FastAPI + React/Vite experience for registering, logging in, and submitting hazy media for enhancement.

## Backend (FastAPI)

1. Create a virtual environment and install dependencies:
   ```bash
   cd video_dehaze_project
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Copy the sample environment file and update values as needed:
   ```bash
   copy .env.example .env
   ```
   Fill in your MySQL credentials and JWT secret.
3. Run database migrations (first run auto-creates the table) and start the API:
   ```bash
   python backend.py
   ```

The API serves `/docs` for Swagger, `/dehaze` for processing (protected by JWT), and `/results/*` for media downloads. Default file cap is 50 MB per request.

### Neural dehazing models (optional)

1. Download an FFA-Net checkpoint (e.g., the official `FFA-Net/FFA-Net.pth`) and place it anywhere on disk.
2. Edit `.env` and set:
   ```
   DEHAZE_IMAGE_MODEL=ffa_net        # or keep `clahe`
   DEHAZE_VIDEO_MODEL=ffa_net        # applies per-frame during video runs
   DEHAZE_FFA_WEIGHTS=C:/path/to/FFA-Net.pth
   ```
3. Install PyTorch if you have not already (included in `requirements.txt`). The service will auto-load the network on startup and silently fall back to CLAHE if the weights/device are unavailable.

Clients can also override the model per-request by submitting `model_choice` (`auto`, `ffa_net`, or `clahe`) alongside `dehaze_type`.

## Frontend (React + Vite + Tailwind)

1. Install Node dependencies:
   ```bash
   cd frontend
   npm install
   ```
2. Configure the API base URL:
   ```bash
   copy .env.example .env
   ```
3. Launch the dev server:
   ```bash
   npm run dev
   ```

The frontend defaults to `http://127.0.0.1:8000` but you can point it at any deployed API via `VITE_API_URL`. Inside the dashboard you can switch between Image/Video modes and choose which model to run (`Auto`, `FFA-Net`, or the CLAHE fallback) per request.

For production builds use `npm run build`, then serve the generated `frontend/dist` folder (the FastAPI `home` route will look for it automatically).

