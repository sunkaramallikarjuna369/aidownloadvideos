"""
API routes for the course downloader application.
This module contains all the FastAPI route handlers.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
import os
import json
import time
import zipfile
import io
import uuid
import requests
from typing import Dict, Any

from app.models.schemas import (
    LoginRequest, 
    APILoginRequest, 
    DownloadRequest, 
    VideoDownloadRequest
)
from app.core.config import DEFAULT_DOWNLOAD_DIR, USER_AGENT
from app.core.state import (
    sessions, 
    download_progress, 
    get_session, 
    set_session, 
    delete_session as del_session,
    get_progress,
    set_progress
)
from app.services.selenium_driver import get_chrome_driver
from app.services.auth import is_qpiai_explorer, login_qpiai_explorer, get_jwt_token
from app.services.export import save_videos_to_files, save_course_structure
from app.services.downloader import download_videos_batch, sanitize_filename

# Create router
router = APIRouter()


@router.get("/healthz")
async def healthz():
    """Health check endpoint."""
    return {"status": "ok"}


@router.get("/sessions")
async def list_sessions():
    """List all active sessions."""
    return {
        "sessions": [
            {
                "id": sid,
                "modules_count": len(data.get("modules", [])),
                "created_at": data.get("created_at", "unknown")
            }
            for sid, data in sessions.items()
        ]
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    if del_session(session_id):
        return {"success": True}
    raise HTTPException(status_code=404, detail="Session not found")


@router.get("/downloads")
async def list_downloads():
    """List downloaded files."""
    downloads = []
    if os.path.exists(DEFAULT_DOWNLOAD_DIR):
        for item in os.listdir(DEFAULT_DOWNLOAD_DIR):
            item_path = os.path.join(DEFAULT_DOWNLOAD_DIR, item)
            if os.path.isdir(item_path):
                downloads.append({
                    "name": item,
                    "type": "folder",
                    "path": item_path
                })
    return {"downloads": downloads}


@router.get("/progress/{session_id}")
async def get_download_progress(session_id: str):
    """Get download progress for a session."""
    progress = get_progress(session_id)
    if progress:
        return progress
    return {"status": "not_found", "progress": 0}


@router.post("/download-zip/{session_id}")
async def download_zip(session_id: str):
    """Download all files for a session as a ZIP."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    download_path = session.get("download_path", DEFAULT_DOWNLOAD_DIR)
    
    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(download_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, download_path)
                zip_file.write(file_path, arcname)
    
    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=course_content_{session_id}.zip"}
    )
