import os
import httpx
import asyncio
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import aiofiles
from pydub import AudioSegment

from monitoring import init_database, log_request, get_today_stats, send_daily_summary, get_seconds_until_midnight

# .env-Datei laden
load_dotenv()

# Thread Pool fuer blockierende Operationen
max_workers = os.getenv("MAX_CONCURRENT_ENHANCEMENTS", "5")
executor = ThreadPoolExecutor(max_workers=int(max_workers) if max_workers else 5)

# FastAPI App initialisieren
app = FastAPI(title="Audio Enhancer API", version="1.0.0")

# Konfiguration
AI_COUSTICS_API_KEY = os.getenv("AI_COUSTICS_API_KEY")
AI_COUSTICS_API_URL = "https://api.ai-coustics.io/v1"
UPLOAD_MAX_SIZE_MB = int(os.getenv("UPLOAD_MAX_SIZE_MB", "100") or "100")
STORAGE_DAYS = int(os.getenv("STORAGE_DAYS", "7") or "7")
ENHANCED_DIR = Path("data/enhanced")

# Ensure enhanced directory exists
ENHANCED_DIR.mkdir(parents=True, exist_ok=True)

# Audio Presets fuer Social Media
AUDIO_PRESETS = {
    "instagram_story": {
        "name": "Instagram Story",
        "loudness_target": -14,
        "loudness_peak": -1,
        "enhancement_level": 0.8,
        "description": "Optimiert fuer Instagram Stories"
    },
    "youtube": {
        "name": "YouTube",
        "loudness_target": -14,
        "loudness_peak": -1,
        "enhancement_level": 1.0,
        "description": "YouTube Standard-Lautstaerke"
    },
    "podcast": {
        "name": "Podcast",
        "loudness_target": -16,
        "loudness_peak": -1,
        "enhancement_level": 1.0,
        "description": "Optimiert fuer Podcasts und Sprache"
    },
    "tiktok": {
        "name": "TikTok",
        "loudness_target": -14,
        "loudness_peak": -1,
        "enhancement_level": 0.9,
        "description": "Optimiert fuer TikTok Videos"
    },
    "custom": {
        "name": "Benutzerdefiniert",
        "loudness_target": -14,
        "loudness_peak": -1,
        "enhancement_level": 1.0,
        "description": "Eigene Einstellungen"
    }
}

async def schedule_daily_summary():
    """Schedule daily summary to be sent before midnight"""
    while True:
        try:
            seconds_until_midnight = get_seconds_until_midnight()
            
            if seconds_until_midnight <= 600:  # Less than 10 minutes to midnight
                await asyncio.sleep(seconds_until_midnight + 10)
                seconds_until_midnight = get_seconds_until_midnight()
            
            # Wait until 23:50
            await asyncio.sleep(seconds_until_midnight - 600)
            
            # Send daily summary
            await send_daily_summary()
            
            # Wait until after midnight
            await asyncio.sleep(700)
        except Exception as e:
            print(f"Daily summary scheduler error: {e}")
            await asyncio.sleep(3600)

@app.on_event("startup")
async def startup_event():
    """Initialize database and start background tasks on startup"""
    await init_database()
    # Start daily summary scheduler
    asyncio.create_task(schedule_daily_summary())
    # Start cleanup task
    from cleanup import start_cleanup_task
    asyncio.create_task(start_cleanup_task())

# Static Files fuer Frontend
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS-Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "ALLOWALL"
    response.headers["Content-Security-Policy"] = "frame-ancestors *"
    return response

def generate_file_hash(content: bytes) -> str:
    """Generate a unique hash for file content"""
    return hashlib.sha256(content).hexdigest()[:12]

async def get_audio_duration(file_path: Path) -> float:
    """Get audio duration in seconds"""
    try:
        audio = await asyncio.get_event_loop().run_in_executor(
            executor,
            lambda: AudioSegment.from_file(str(file_path))
        )
        return len(audio) / 1000.0  # Convert to seconds
    except Exception as e:
        print(f"Error getting audio duration: {e}")
        return 0.0

async def enhance_audio_with_ai_coustics(
    file_data: bytes,
    file_type: str,
    preset: str = "custom",
    custom_params: Optional[dict] = None
) -> tuple[bytes, str]:
    """Call ai-coustics API to enhance audio"""
    
    if not AI_COUSTICS_API_KEY:
        raise HTTPException(status_code=500, detail="AI Coustics API key not configured")
    
    # Get preset parameters
    preset_params = AUDIO_PRESETS.get(preset, AUDIO_PRESETS["custom"])
    
    # Use custom parameters if provided
    if custom_params:
        params = custom_params
    else:
        params = {
            "loudness_target_level": preset_params["loudness_target"],
            "loudness_peak_limit": preset_params["loudness_peak"],
            "enhancement_level": preset_params["enhancement_level"]
        }
    
    # Determine output format
    output_format = "MP3" if "mp3" in file_type.lower() else "WAV"
    params["transcode_kind"] = output_format
    
    async with httpx.AsyncClient(timeout=300.0) as client:  # 5 minute timeout
        try:
            # Prepare multipart form data
            files = {
                "file": ("audio", file_data, file_type)
            }
            
            # Send request to ai-coustics API
            response = await client.post(
                f"{AI_COUSTICS_API_URL}/media/enhance",
                files=files,
                data=params,
                headers={"X-API-Key": AI_COUSTICS_API_KEY}
            )
            
            if response.status_code == 201:
                result = response.json()
                generated_name = result.get("generated_name")
                
                if not generated_name:
                    raise HTTPException(status_code=500, detail="No file name returned from API")
                
                # Download the enhanced file
                download_response = await client.get(
                    f"{AI_COUSTICS_API_URL}/media/{generated_name}",
                    headers={"X-API-Key": AI_COUSTICS_API_KEY}
                )
                
                if download_response.status_code == 200:
                    return download_response.content, generated_name
                else:
                    raise HTTPException(
                        status_code=download_response.status_code,
                        detail=f"Failed to download enhanced file: {download_response.text}"
                    )
                    
            else:
                error_detail = response.text
                if response.status_code == 402:
                    error_detail = "API quota exceeded. Please try again later."
                elif response.status_code == 415:
                    error_detail = "Unsupported file format. Only MP3 and WAV are supported."
                    
                raise HTTPException(status_code=response.status_code, detail=error_detail)
                
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Enhancement timeout. File may be too large.")
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=f"Enhancement failed: {str(e)}")

@app.get("/", response_class=HTMLResponse)
async def get_frontend():
    """Audio Enhancement Frontend"""
    try:
        with open("static/enhance.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Frontend not found</h1>", status_code=500)

@app.get("/api/presets")
async def get_presets():
    """Get available audio presets"""
    return {"presets": AUDIO_PRESETS}

@app.post("/api/enhance")
async def enhance_audio(
    file: UploadFile = File(...),
    preset: str = Form("custom"),
    loudness_target: Optional[int] = Form(None),
    loudness_peak: Optional[int] = Form(None),
    enhancement_level: Optional[float] = Form(None)
):
    """Enhance audio file endpoint"""
    
    # Validate file type
    if not file.content_type or not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Only audio files are allowed")
    
    # Check file size
    if file.size and file.size > UPLOAD_MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum {UPLOAD_MAX_SIZE_MB}MB allowed")
    
    # Read file data
    file_data = await file.read()
    
    # Additional size check
    if len(file_data) > UPLOAD_MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum {UPLOAD_MAX_SIZE_MB}MB allowed")
    
    # Prepare custom parameters if provided
    custom_params = None
    if preset == "custom" and any([loudness_target, loudness_peak, enhancement_level]):
        custom_params = {}
        if loudness_target is not None:
            custom_params["loudness_target_level"] = max(-70, min(-5, loudness_target))
        if loudness_peak is not None:
            custom_params["loudness_peak_limit"] = max(-9, min(0, loudness_peak))
        if enhancement_level is not None:
            custom_params["enhancement_level"] = max(0, min(1, enhancement_level))
    
    start_time = datetime.now()
    
    try:
        # Save original file temporarily for duration calculation
        temp_file_hash = generate_file_hash(file_data)
        temp_file_path = ENHANCED_DIR / f"temp_{temp_file_hash}"
        
        async with aiofiles.open(temp_file_path, "wb") as f:
            await f.write(file_data)
        
        # Get audio duration
        audio_duration = await get_audio_duration(temp_file_path)
        
        # Enhance audio
        enhanced_data, api_file_name = await enhance_audio_with_ai_coustics(
            file_data,
            file.content_type,
            preset,
            custom_params
        )
        
        # Generate filename for storage
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_extension = "mp3" if "mp3" in file.content_type.lower() else "wav"
        enhanced_filename = f"enhanced_{timestamp}_{api_file_name}.{file_extension}"
        enhanced_path = ENHANCED_DIR / enhanced_filename
        
        # Save enhanced file
        async with aiofiles.open(enhanced_path, "wb") as f:
            await f.write(enhanced_data)
        
        # Clean up temp file
        temp_file_path.unlink(missing_ok=True)
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Log successful request
        await log_request(
            success=True,
            preset=preset,
            duration_seconds=audio_duration,
            processing_time=processing_time,
            file_size_mb=len(file_data) / (1024 * 1024)
        )
        
        return {
            "success": True,
            "filename": enhanced_filename,
            "download_url": f"/api/download/{enhanced_filename}",
            "processing_time": round(processing_time, 2),
            "audio_duration": round(audio_duration, 2),
            "preset_used": preset
        }
        
    except Exception as e:
        # Clean up temp file on error
        if 'temp_file_path' in locals():
            temp_file_path.unlink(missing_ok=True)
            
        # Log failed request
        await log_request(success=False, preset=preset, error=str(e))
        
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Enhancement failed: {str(e)}")

@app.get("/api/download/{filename}")
async def download_enhanced_file(filename: str):
    """Download enhanced audio file"""
    
    # Validate filename (prevent directory traversal)
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    file_path = ENHANCED_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Determine media type
    media_type = "audio/mpeg" if filename.endswith(".mp3") else "audio/wav"
    
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename
    )

@app.get("/api/stats")
async def get_stats():
    """Get today's enhancement statistics"""
    return await get_today_stats()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)