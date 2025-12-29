"""
Pydantic models for request/response schemas.
"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any


# ============ Authentication Models ============

class LoginRequest(BaseModel):
    """Request model for course login."""
    course_url: str
    username: str
    password: str


class APILoginRequest(BaseModel):
    """Request model for API-based login (QpiAI specific)."""
    course_url: str
    email: str
    password: str


# ============ Module/Content Models ============

class ModuleInfo(BaseModel):
    """Information about a course module."""
    id: str
    name: str
    items: List[Dict[str, Any]]


class VideoInfo(BaseModel):
    """Information about a video."""
    module: str
    chapter: str
    title: str
    url: str
    lesson_url: Optional[str] = None


# ============ Download Models ============

class DownloadRequest(BaseModel):
    """Request model for downloading modules."""
    session_id: str
    module_ids: List[str]
    download_path: str = ""  # Optional custom download path


class VideoDownloadRequest(BaseModel):
    """Request model for downloading videos."""
    session_id: str
    videos: List[Dict[str, Any]]
    download_path: str = ""


# ============ Response Models ============

class LoginResponse(BaseModel):
    """Response model for login."""
    success: bool
    session_id: Optional[str] = None
    modules: List[Dict[str, Any]] = []
    message: Optional[str] = None


class ExtractResponse(BaseModel):
    """Response model for video extraction."""
    success: bool
    session_id: Optional[str] = None
    total_videos: int = 0
    total_lessons: int = 0
    videos: List[Dict[str, Any]] = []
    files_saved: Optional[Dict[str, str]] = None
    message: Optional[str] = None


class DownloadProgressResponse(BaseModel):
    """Response model for download progress."""
    status: str
    progress: float
    current_file: Optional[str] = None
    completed: int = 0
    total: int = 0
    errors: List[str] = []
