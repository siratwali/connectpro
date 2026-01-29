"""
LinkedIn Auto Connect Pro - FastAPI Backend with Activity Logging
Fixed Version - Proper file cleanup and session management
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from threading import Thread
import pandas as pd
import uvicorn
import secrets
import logging
import linkedin_bot
import os
import time

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== DIRECTORIES ====================
BASE_DIR = Path(__file__).parent
PUBLIC_DIR = BASE_DIR / "public"
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

# ==================== APP INIT ====================
app = FastAPI(
    title="LinkedIn Auto Connect Pro",
    description="Share this link with clients",
    version="2.0.0"
)

# CORS - allow all origins (optimized)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== JOBS STORAGE ====================
# In-memory storage for fast access
JOBS = {}

# ==================== HELPER FUNCTIONS ====================
def cleanup_files(csv_path: str = None, result_file: str = None):
    """Delete uploaded CSV and result files"""
    try:
        if csv_path and os.path.exists(csv_path):
            os.remove(csv_path)
            logger.info(f"Deleted CSV file: {csv_path}")
        
        if result_file and os.path.exists(result_file):
            os.remove(result_file)
            logger.info(f"Deleted result file: {result_file}")
    except Exception as e:
        logger.error(f"Error cleaning up files: {str(e)}")

def cleanup_old_uploads():
    """Clean all files in uploads directory"""
    try:
        for file in UPLOADS_DIR.glob("*"):
            if file.is_file():
                os.remove(file)
                logger.info(f"Cleaned up old upload: {file}")
    except Exception as e:
        logger.error(f"Error cleaning uploads directory: {str(e)}")

# ==================== ENDPOINTS ====================
@app.get("/ping")
def ping():
    return {"status": "alive"}

@app.on_event("startup")
def reset_jobs():
    """Reset jobs and clean up old files on startup"""
    global JOBS
    JOBS = {}
    cleanup_old_uploads()
    # Clean any existing result files
    try:
        if os.path.exists("results.csv"):
            os.remove("results.csv")
        if os.path.exists("file.csv"):
            os.remove("file.csv")
    except Exception as e:
        logger.error(f"Error cleaning result files: {str(e)}")

@app.get("/", response_class=FileResponse)
def serve_frontend():
    html_file = PUBLIC_DIR / "client.html"
    if not html_file.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(html_file)

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "LinkedIn Auto Connect Pro",
        "version": "2.0.0"
    }

# Job Status endpoint - Fast response with minimal data
@app.get("/api/job-status/{job_id}")
def get_job_status(job_id: str):
    if job_id not in JOBS:
        return JSONResponse(
            status_code=404,
            content={"status": "not_found", "done": 0, "total": 0}
        )
    
    job = JOBS[job_id]
    
    # Return only essential data for faster response
    return {
        "status": job.get("status", "processing"),
        "done": job.get("done", 0),
        "total": job.get("total", 0),
        "result_file": job.get("result_file", ""),
        "activity_log": job.get("activity_log", [])[-10:],  # Only last 10 logs for speed
        "error": job.get("error", None)
    }

# Download results file endpoint
@app.get("/download/{filename}")
def download_file(filename: str):
    file_path = BASE_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Schedule file cleanup after download (give 5 seconds for download to complete)
    def delayed_cleanup():
        time.sleep(5)
        cleanup_files(result_file=str(file_path))
    
    Thread(target=delayed_cleanup, daemon=True).start()
    
    return FileResponse(file_path, media_type='text/csv', filename=filename)

@app.post("/api/process-csv")
async def process_csv(
    email: str = Form(...),
    password: str = Form(...),
    dailylimit: int = Form(...),
    file: UploadFile = File(...)
):
    try:
        # Quick validation
        if not email or not password:
            return JSONResponse(status_code=400, content={"detail": "Email and password required"})
        
        if dailylimit < 1 or dailylimit > 150:
            return JSONResponse(status_code=400, content={"detail": f"Daily limit must be between 1-150"})
        
        if not file or not file.filename.endswith(".csv"):
            return JSONResponse(status_code=400, content={"detail": "Valid CSV file required"})

        # Clean old files
        cleanup_old_uploads()
        if os.path.exists("results.csv"):
            os.remove("results.csv")

        # Save CSV
        file_path = UPLOADS_DIR / f"{secrets.token_hex(8)}.csv"
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)

        # Quick CSV validation
        df = pd.read_csv(file_path)
        urls = df.iloc[:, 0].dropna().tolist()

        if len(urls) == 0:
            cleanup_files(csv_path=str(file_path))
            return JSONResponse(status_code=400, content={"detail": "CSV has no URLs"})

        actual_limit = min(dailylimit, len(urls))
        job_id = secrets.token_hex(6)

        # Initialize job with minimal data
        JOBS[job_id] = {
            "status": "processing",
            "done": 0,
            "total": len(urls),
            "result_file": "results.csv",
            "csv_path": str(file_path),
            "activity_log": [
                f"📋 Processing {len(urls)} LinkedIn profiles",
                f"⏱️ Daily limit: {actual_limit}"
            ]
        }

        # Configure bot
        linkedin_bot.EMAIL = email
        linkedin_bot.PASSWORD = password
        linkedin_bot.DAILY_LIMIT = actual_limit
        linkedin_bot.CSV_FILE = str(file_path)
        linkedin_bot.OUTPUT_FILE = "results.csv"
        linkedin_bot.JOB_ID = job_id
        linkedin_bot.JOBS = JOBS

        # Run bot with cleanup
        def run_bot_with_cleanup():
            try:
                linkedin_bot.main()
            finally:
                time.sleep(2)
                cleanup_files(csv_path=str(file_path))

        Thread(target=run_bot_with_cleanup, daemon=True).start()

        return JSONResponse({
            "status": "processing",
            "message": f"Processing {len(urls)} profiles",
            "job_id": job_id
        })

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": f"Server error: {str(e)}"})

# Serve client HTML (optional token)
@app.get("/client/{token}")
def client_page(token: str):
    html_file = PUBLIC_DIR / "client.html"
    if not html_file.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    logger.info(f"Client page accessed with token: {token}")
    return FileResponse(html_file)

@app.get("/client")
def client_page_default():
    html_file = PUBLIC_DIR / "client.html"
    if not html_file.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(html_file)

if __name__ == "__main__":
    # Optimized server configuration
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="warning",  # Reduce logging overhead
        access_log=False,     # Disable access logs for speed
        workers=1             # Single worker to maintain shared state
    )
