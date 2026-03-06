from fastapi import FastAPI, UploadFile, Form, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uvicorn
import cv2
import numpy as np
import base64
import tempfile
import os
from pathlib import Path
import jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from utils.dehaze import (
    SUPPORTED_IMAGE_MODELS,
    SUPPORTED_VIDEO_MODELS,
    dehaze_image,
    dehaze_video_frame,
)
import uuid
import shutil
import subprocess
from sqlalchemy import Column, DateTime, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = FastAPI()

# Allow frontend calls
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Expose results directory for processed videos
RESULTS_DIR = os.path.join(BASE_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

@app.get("/results/{filename}")
def get_result_file(filename: str):
    file_path = os.path.join(RESULTS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    # Set explicit media type to help browsers choose decoder
    media_type = "application/octet-stream"
    lower = filename.lower()
    if lower.endswith(".mp4"):
        media_type = "video/mp4"
    elif lower.endswith(".avi"):
        media_type = "video/x-msvideo"
    return FileResponse(file_path, media_type=media_type)

# Database configuration
DB_USER = os.environ.get("DEHAZE_DB_USER", "root")
DB_PASSWORD = os.environ.get("DEHAZE_DB_PASSWORD", "anas019")
DB_HOST = os.environ.get("DEHAZE_DB_HOST", "localhost")
DB_PORT = os.environ.get("DEHAZE_DB_PORT", "3306")
DB_NAME = os.environ.get("DEHAZE_DB_NAME", "video_dehaze")
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Auth configuration
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
security = HTTPBearer()
SECRET_KEY = os.environ.get("DEHAZE_SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12

def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(subject: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> str:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

@app.post("/register")
async def register(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    if not username or not password:
        return {"status": "error", "message": "Username and password are required"}
    if len(password) > 256:
        return {"status": "error", "message": "Password too long"}
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        return {"status": "error", "message": "Username already exists"}
    hashed_password = hash_password(password)
    new_user = User(username=username, password_hash=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"status": "success", "message": "Registration successful"}

@app.post("/login")
async def login(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return {"status": "error", "message": "Invalid username or password"}
    if not verify_password(password, user.password_hash):
        return {"status": "error", "message": "Invalid username or password"}
    token = create_access_token(username)
    return {"status": "success", "message": "Login successful", "token": token}

MODEL_CHOICES = SUPPORTED_IMAGE_MODELS.union(SUPPORTED_VIDEO_MODELS)


@app.post("/dehaze")
async def dehaze(
    file: UploadFile = None,
    dehaze_type: str = Form(...),
    model_choice: str = Form("auto"),
    current_user: str = Depends(get_current_user)
):
    try:
        if not file:
            return {"status": "error", "message": "No file uploaded"}
        if dehaze_type not in ("image", "video"):
            return {"status": "error", "message": "dehaze_type must be 'image' or 'video'"}
        model_choice = (model_choice or "auto").lower()
        if model_choice not in MODEL_CHOICES:
            return {"status": "error", "message": f"Unsupported model '{model_choice}'"}

        # Limit file size (e.g., 50MB)
        contents = await file.read()
        if len(contents) > 50 * 1024 * 1024:
            return {"status": "error", "message": "File too large (max 50MB)"}

        if dehaze_type == "image":
            npimg = np.frombuffer(contents, np.uint8)
            frame = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
            if frame is None:
                return {"status": "error", "message": "Invalid image file"}
            
            # Get original resolution
            original_height, original_width = frame.shape[:2]
            original_resolution = f"{original_width}x{original_height}"
            
            # Dehaze the image
            enhanced = dehaze_image(frame, model_hint=model_choice)
            
            # Get enhanced resolution (should be same, but let's verify)
            enhanced_height, enhanced_width = enhanced.shape[:2]
            enhanced_resolution = f"{enhanced_width}x{enhanced_height}"
            
            # Check if resolution changed (it shouldn't, but verify)
            resolution_changed = (original_width != enhanced_width) or (original_height != enhanced_height)
            
            # Calculate proper haze removal percentage using established image quality metrics
            
            def calculate_dark_channel(img, patch_size=15):
                """
                Calculate Dark Channel Prior - a key metric for haze estimation.
                Lower values indicate less haze (better dehazing).
                Based on the Dark Channel Prior theory by He et al.
                """
                # Convert to float and normalize
                img_float = img.astype(np.float32) / 255.0
                # Get minimum channel value for each pixel
                min_channel = np.min(img_float, axis=2)
                # Apply minimum filter (patch_size x patch_size)
                kernel = np.ones((patch_size, patch_size), np.float32)
                dark_channel = cv2.erode(min_channel, kernel)
                return float(np.mean(dark_channel))
            
            def calculate_gradient_magnitude(img):
                """
                Calculate average gradient magnitude - measures image sharpness.
                Higher values indicate sharper image (better dehazing).
                """
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
                grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
                grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
                magnitude = np.sqrt(grad_x**2 + grad_y**2)
                return float(np.mean(magnitude))
            
            def calculate_color_saturation(img):
                """
                Calculate color saturation - hazy images are desaturated.
                Higher saturation indicates better dehazing.
                """
                hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
                saturation = hsv[:, :, 1].astype(np.float32)
                return float(np.mean(saturation))
            
            def calculate_visibility_metric(img):
                """
                Calculate visibility using contrast and edge strength.
                Combines multiple factors for comprehensive visibility assessment.
                """
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
                # Local contrast (standard deviation in local patches)
                kernel = np.ones((5, 5), np.float32) / 25
                local_mean = cv2.filter2D(gray, -1, kernel)
                local_std = np.sqrt(cv2.filter2D((gray - local_mean)**2, -1, kernel))
                contrast_score = float(np.mean(local_std))
                
                # Edge strength
                laplacian = cv2.Laplacian(gray, cv2.CV_64F)
                edge_strength = float(np.var(laplacian))
                
                # Combined visibility metric (normalized)
                visibility = (contrast_score / 50.0 + edge_strength / 1000.0) / 2.0
                return min(1.0, max(0.0, visibility))
            
            # Calculate metrics for original and enhanced images
            original_dark_channel = calculate_dark_channel(frame)
            enhanced_dark_channel = calculate_dark_channel(enhanced)
            
            original_gradient = calculate_gradient_magnitude(frame)
            enhanced_gradient = calculate_gradient_magnitude(enhanced)
            
            original_saturation = calculate_color_saturation(frame)
            enhanced_saturation = calculate_color_saturation(enhanced)
            
            original_visibility = calculate_visibility_metric(frame)
            enhanced_visibility = calculate_visibility_metric(enhanced)
            
            # Calculate improvement percentages for each metric
            # Dark channel: lower is better, so improvement = (original - enhanced) / original
            dark_channel_improvement = 0
            if original_dark_channel > 0:
                dark_channel_improvement = ((original_dark_channel - enhanced_dark_channel) / original_dark_channel) * 100
                dark_channel_improvement = max(0, min(100, dark_channel_improvement))
            
            # Gradient: higher is better
            gradient_improvement = 0
            if original_gradient > 0:
                gradient_improvement = ((enhanced_gradient - original_gradient) / original_gradient) * 100
                gradient_improvement = max(0, min(200, gradient_improvement))  # Allow up to 200% improvement
            
            # Saturation: higher is better
            saturation_improvement = 0
            if original_saturation > 0:
                saturation_improvement = ((enhanced_saturation - original_saturation) / original_saturation) * 100
                saturation_improvement = max(0, min(200, saturation_improvement))
            
            # Visibility: higher is better (0-1 scale, convert to percentage)
            visibility_improvement = ((enhanced_visibility - original_visibility) / max(original_visibility, 0.01)) * 100
            visibility_improvement = max(0, min(200, visibility_improvement))
            
            # Calculate overall haze removal percentage using weighted combination
            # Dark channel is most important (40%) as it directly measures haze
            # Visibility is also crucial (30%) as it measures overall image quality
            # Gradient (20%) measures sharpness improvement
            # Saturation (10%) measures color restoration
            overall_improvement = (
                dark_channel_improvement * 0.4 +
                visibility_improvement * 0.3 +
                min(100, gradient_improvement) * 0.2 +
                min(100, saturation_improvement) * 0.1
            )
            
            # Normalize to 0-100 range
            overall_improvement = max(0, min(100, overall_improvement))
            
            # Encode both original and enhanced images
            _, enhanced_buffer = cv2.imencode(".jpg", enhanced)
            enhanced_base64 = base64.b64encode(enhanced_buffer).decode("utf-8")
            
            _, original_buffer = cv2.imencode(".jpg", frame)
            original_base64 = base64.b64encode(original_buffer).decode("utf-8")
            
            return JSONResponse(content={
                "status": "success",
                "message": "image dehazing done",
                "image": enhanced_base64,
                "original_image": original_base64,
                "model": model_choice,
                "resolution": {
                    "before": original_resolution,
                    "after": enhanced_resolution,
                    "changed": resolution_changed
                },
                "improvement": {
                    "percentage": round(overall_improvement, 2),
                    "dark_channel": round(dark_channel_improvement, 2),
                    "visibility": round(visibility_improvement, 2),
                    "gradient": round(gradient_improvement, 2),
                    "saturation": round(saturation_improvement, 2)
                }
            })

        # video processing path
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "input_video")
            # generate unique output name in persistent results dir
            out_name = f"out_{uuid.uuid4().hex}.mp4"
            out_path = os.path.join(RESULTS_DIR, out_name)
            with open(in_path, "wb") as f:
                f.write(contents)

            cap = cv2.VideoCapture(in_path)
            if not cap.isOpened():
                return {"status": "error", "message": "Invalid or unsupported video file"}

            # Derive sane parameters
            fps = cap.get(cv2.CAP_PROP_FPS)
            if not fps or fps <= 0 or fps != fps:  # NaN check
                fps = 25.0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if width <= 0 or height <= 0:
                cap.release()
                return {"status": "error", "message": "Could not read video resolution"}

            # Try MP4 first
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(out_path, fourcc, fps, (width, height))
            use_avi_fallback = False
            if not writer.isOpened():
                # Fallback to AVI/XVID, update persistent output path and name
                writer.release()
                out_name = f"out_{uuid.uuid4().hex}.avi"
                out_path = os.path.join(RESULTS_DIR, out_name)
                fourcc = cv2.VideoWriter_fourcc(*"XVID")
                writer = cv2.VideoWriter(out_path, fourcc, fps, (width, height))
                use_avi_fallback = True
                if not writer.isOpened():
                    cap.release()
                    return {"status": "error", "message": "Failed to initialize video encoder"}

            processed_frames = 0
            max_frames = 1500  # safety cap
            while processed_frames < max_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                enhanced = dehaze_video_frame(frame, model_hint=model_choice)
                writer.write(enhanced)
                processed_frames += 1

            cap.release()
            writer.release()

            # Verify output exists and non-empty
            if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
                return {"status": "error", "message": "Video processing produced empty output"}

            # Attempt to ensure browser-playable H.264 MP4 using ffmpeg if available
            final_name = out_name
            final_mime = "video/avi" if use_avi_fallback else "video/mp4"
            ffmpeg_path = shutil.which("ffmpeg")
            if ffmpeg_path:
                try:
                    # Detect hardware acceleration support
                    def detect_hw_encoder():
                        """Try to detect available hardware encoder"""
                        test_cmd = [ffmpeg_path, "-hide_banner", "-encoders"]
                        try:
                            result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=5)
                            encoders = result.stdout.lower()
                            # Check for NVIDIA NVENC
                            if "h264_nvenc" in encoders:
                                return "h264_nvenc"
                            # Check for Intel Quick Sync
                            if "h264_qsv" in encoders:
                                return "h264_qsv"
                            # Check for AMD AMF
                            if "h264_amf" in encoders:
                                return "h264_amf"
                            # Check for Apple VideoToolbox
                            if "h264_videotoolbox" in encoders:
                                return "h264_videotoolbox"
                        except Exception:
                            pass
                        return None
                    
                    hw_encoder = detect_hw_encoder()
                    src_path = out_path
                    h264_name = f"out_{uuid.uuid4().hex}_h264.mp4"
                    h264_path = os.path.join(RESULTS_DIR, h264_name)
                    
                    # Build optimized ffmpeg command
                    cmd = [ffmpeg_path, "-y", "-i", src_path]
                    
                    if hw_encoder:
                        # Use hardware acceleration for much faster encoding
                        cmd.extend(["-vcodec", hw_encoder])
                        if hw_encoder == "h264_nvenc":
                            cmd.extend(["-preset", "p1", "-cq", "23"])  # NVIDIA: p1=fastest, p7=slowest
                        elif hw_encoder == "h264_qsv":
                            cmd.extend(["-preset", "veryfast", "-global_quality", "23"])
                        elif hw_encoder == "h264_amf":
                            cmd.extend(["-quality", "speed", "-rc", "cqp", "-qp_i", "23", "-qp_p", "23"])
                        elif hw_encoder == "h264_videotoolbox":
                            cmd.extend(["-b:v", "5M", "-allow_sw", "1"])
                    else:
                        # Fallback to software encoding with maximum speed optimizations
                        cmd.extend([
                            "-vcodec", "libx264",
                            "-preset", "ultrafast",  # Fastest software preset
                            "-tune", "zerolatency",  # Optimize for speed
                            "-crf", "23",
                            "-threads", "0",  # Auto-detect optimal thread count
                        ])
                    
                    # Common options for all encoders
                    cmd.extend([
                        "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart",  # Enable progressive playback
                        "-an",  # No audio stream
                        h264_path
                    ])
                    
                    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
                    if os.path.exists(h264_path) and os.path.getsize(h264_path) > 0:
                        final_name = h264_name
                        final_mime = "video/mp4"
                except subprocess.TimeoutExpired:
                    # If encoding takes too long, keep original file
                    pass
                except Exception:
                    # If ffmpeg fails, keep original file
                    pass

            return JSONResponse(content={
                "status": "success",
                "message": "video dehazing done",
                "url": f"/results/{final_name}",
                "mime": final_mime,
                "model": model_choice
            })

    except Exception as e:
        return {"status": "error", "message": str(e)}

# Serve frontend (built assets first, fall back to dev template)
FRONTEND_DIST = os.path.join(BASE_DIR, "frontend", "dist", "index.html")
FRONTEND_TEMPLATE = os.path.join(BASE_DIR, "frontend", "index.html")


@app.get("/", response_class=HTMLResponse)
def home():
    """Serve the SPA entrypoint if it exists"""
    for candidate in (FRONTEND_DIST, FRONTEND_TEMPLATE):
        if os.path.exists(candidate):
            with open(candidate, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
    return HTMLResponse(
        content="<html><body><h1>Backend is running!</h1>"
        "<p>Frontend build not found. Run <code>npm run dev</code> inside <code>frontend/</code>."
        " Visit <a href='/docs'>/docs</a> for API endpoints.</p></body></html>"
    )


# Uvicorn is used here for development/testing when running the script directly.
# In production, you typically run: uvicorn backend:app --host 0.0.0.0 --port 8000
# This block allows running: python backend.py
if __name__ == "__main__":
    uvicorn.run("backend:app", host="0.0.0.0", port=8000, reload=True)
