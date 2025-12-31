"""
LinkedIn Auto Connect Pro - FastAPI Backend with Activity Logging
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

# CORS - allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== JOBS STORAGE ====================
# Track multiple CSV processing tasks with activity log
JOBS = {}

# ==================== ENDPOINTS ====================

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

# Progress endpoint - BOTH names for compatibility
@app.get("/api/progress/{job_id}")
def get_progress(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    return JOBS[job_id]

# Job Status endpoint - Frontend calls this one
@app.get("/api/job-status/{job_id}")
def get_job_status(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    return JOBS[job_id]

# Download results file endpoint
@app.get("/download/{filename}")
def download_file(filename: str):
    file_path = BASE_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type='text/csv', filename=filename)

@app.post("/api/process-csv")
async def process_csv(
    email: str = Form(...),
    password: str = Form(...),
    daily_limit: int = Form(50),
    file: UploadFile = File(...)
):
    try:
        if not email or not password:
            raise HTTPException(status_code=400, detail="Email and password required")
        if daily_limit < 1 or daily_limit > 150:
            raise HTTPException(status_code=400, detail="Daily limit must be between 1-150")
        if not file or not file.filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="Valid CSV file required")

        # Save CSV temporarily
        file_path = UPLOADS_DIR / f"{secrets.token_hex(8)}.csv"
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)

        df = pd.read_csv(file_path)
        urls = df.iloc[:, 0].dropna().tolist()

        if len(urls) == 0:
            raise HTTPException(status_code=400, detail="CSV first column has no URLs")

        logger.info(f"CSV loaded: {len(urls)} URLs")

        # Create a job ID
        job_id = secrets.token_hex(6)

        # Initialize job with activity log
        JOBS[job_id] = {
            "status": "processing",
            "done": 0,
            "total": len(urls),
            "result_file": "results.csv",
            "activity_log": [
                f"📋 Starting to process {len(urls)} LinkedIn profiles...",
                f"⏱️ Daily limit set to: {daily_limit} connections"
            ]
        }

        # Configure linkedin_bot
        linkedin_bot.EMAIL = email
        linkedin_bot.PASSWORD = password
        linkedin_bot.DAILY_LIMIT = daily_limit
        linkedin_bot.CSV_FILE = str(file_path)

        # Pass JOB_ID and JOBS for real-time progress and activity
        linkedin_bot.JOB_ID = job_id
        linkedin_bot.JOBS = JOBS

        # Run bot in background thread
        thread = Thread(target=linkedin_bot.main, daemon=True)
        thread.start()

        logger.info(f"Started LinkedIn bot for {email} with {len(urls)} URLs (Job ID: {job_id})")

        return JSONResponse({
            "status": "processing",
            "message": f"✅ Processing {len(urls)} LinkedIn profiles",
            "job_id": job_id
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in process_csv: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

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
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)