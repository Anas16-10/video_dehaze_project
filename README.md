# Video Dehaze Studio

Modern FastAPI + React/Vite application for enhancing hazy images and videos using OpenCV, CLAHE, and neural dehazing models (FFA-Net).

## Features

- **Image Dehazing**: Fast enhancement of hazy photos.
- **Video Dehazing**: Per-frame processing for video enhancement with H.264 optimization.
- **Secure Authentication**: JWT-based login and registration system.
- **Model Selection**: Choose between Automatic, FFA-Net (Neural), or CLAHE (Classic) models.
- **Premium UI**: Modern, responsive dashboard built with React and Tailwind CSS.

## Tech Stack

- **Backend**: FastAPI, PyTorch, OpenCV, SQLAlchemy, MySQL.
- **Frontend**: React, Vite, Tailwind CSS, Lucide React.
- **Database**: MySQL.

## Prerequisites

- Python 3.10+
- Node.js 18+
- MySQL Server

## Getting Started

### 1. Repository Setup

```bash
git clone https://github.com/Anas16-10/video_dehaze_project.git
cd video_dehaze_project
```

### 2. Backend Setup

1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   Source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r video_dehaze_project/requirements.txt
   ```

2. Configure environment variables:
   ```bash
   cp video_dehaze_project/.env.example video_dehaze_project/.env
   ```
   Update `video_dehaze_project/.env` with your MySQL credentials and a secure `DEHAZE_SECRET_KEY`.

3. Start the API server:
   ```bash
   cd video_dehaze_project
   python backend.py
   ```
   The API will be available at `http://localhost:8000`.

### 3. Frontend Setup

1. Install dependencies:
   ```bash
   cd video_dehaze_project/frontend
   npm install
   ```

2. Start the development server:
   ```bash
   npm run dev
   ```
   The frontend will be available at `http://localhost:5173`.

## Optional: Neural Dehazing (FFA-Net)

To use the FFA-Net neural model:
1. Download `FFA-Net.pth` and place it in the project.
2. Update `DEHAZE_FFA_WEIGHTS` in your `.env` file to point to the weights path.
3. Restart the backend.

## License

MIT
