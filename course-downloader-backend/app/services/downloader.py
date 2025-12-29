"""
Download services for video files.
"""
import os
import re
import asyncio
import aiofiles
import requests
from typing import List, Dict, Any, Callable

from app.core.config import (
    DEFAULT_DOWNLOAD_DIR, 
    USER_AGENT, 
    MAX_CONCURRENT_DOWNLOADS,
    DOWNLOAD_CHUNK_SIZE,
    DOWNLOAD_RETRY_COUNT
)
from app.core.state import set_progress, get_progress


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename by removing invalid characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for filesystem
    """
    # Remove invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Replace multiple spaces with single space
    sanitized = re.sub(r'\s+', ' ', sanitized)
    # Trim to reasonable length
    return sanitized[:200].strip()


async def download_file(
    url: str, 
    filepath: str, 
    session_id: str = None,
    progress_callback: Callable = None
) -> bool:
    """
    Download a file from URL to filepath with retry logic.
    
    Args:
        url: URL to download from
        filepath: Local path to save file
        session_id: Session ID for progress tracking
        progress_callback: Optional callback for progress updates
        
    Returns:
        True if download successful, False otherwise
    """
    headers = {"User-Agent": USER_AGENT}
    
    for attempt in range(DOWNLOAD_RETRY_COUNT):
        try:
            # Check if file already exists (resume support)
            existing_size = 0
            if os.path.exists(filepath):
                existing_size = os.path.getsize(filepath)
                headers["Range"] = f"bytes={existing_size}-"
            
            response = requests.get(url, headers=headers, stream=True, timeout=30)
            
            # Handle range request response
            if response.status_code == 416:  # Range not satisfiable - file complete
                return True
            
            response.raise_for_status()
            
            # Get total size
            total_size = int(response.headers.get('content-length', 0)) + existing_size
            
            # Open file in append mode if resuming
            mode = 'ab' if existing_size > 0 else 'wb'
            
            downloaded = existing_size
            async with aiofiles.open(filepath, mode) as f:
                for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                    if chunk:
                        await f.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback and total_size > 0:
                            progress = (downloaded / total_size) * 100
                            progress_callback(progress, downloaded, total_size)
            
            return True
            
        except Exception as e:
            print(f"Download attempt {attempt + 1} failed for {url}: {e}")
            if attempt < DOWNLOAD_RETRY_COUNT - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    return False


async def download_videos_batch(
    videos: List[Dict[str, Any]],
    session_id: str,
    download_path: str = None
) -> Dict[str, Any]:
    """
    Download multiple videos with progress tracking.
    
    Args:
        videos: List of video dictionaries with module, chapter, title, url
        session_id: Session ID for progress tracking
        download_path: Custom download path (optional)
        
    Returns:
        Dictionary with download results
    """
    download_dir = download_path or DEFAULT_DOWNLOAD_DIR
    os.makedirs(download_dir, exist_ok=True)
    
    total = len(videos)
    completed = 0
    errors = []
    
    # Initialize progress
    set_progress(session_id, {
        "status": "downloading",
        "progress": 0,
        "current_file": "",
        "completed": 0,
        "total": total,
        "errors": []
    })
    
    for i, video in enumerate(videos):
        module = sanitize_filename(video.get('module', 'Unknown'))
        chapter = sanitize_filename(video.get('chapter', 'Unknown'))
        title = sanitize_filename(video.get('title', f'video_{i}'))
        url = video.get('url', '')
        
        if not url:
            errors.append(f"No URL for {title}")
            continue
        
        # Create folder structure
        folder_path = os.path.join(download_dir, module, chapter)
        os.makedirs(folder_path, exist_ok=True)
        
        # Determine file extension
        ext = '.mp4'
        if '.webm' in url:
            ext = '.webm'
        elif '.m3u8' in url:
            ext = '.m3u8'
        
        filepath = os.path.join(folder_path, f"{title}{ext}")
        
        # Update progress
        set_progress(session_id, {
            "status": "downloading",
            "progress": (completed / total) * 100,
            "current_file": title,
            "completed": completed,
            "total": total,
            "errors": errors
        })
        
        # Download file
        success = await download_file(url, filepath, session_id)
        
        if success:
            completed += 1
        else:
            errors.append(f"Failed to download: {title}")
    
    # Final progress update
    set_progress(session_id, {
        "status": "completed" if not errors else "completed_with_errors",
        "progress": 100,
        "current_file": "",
        "completed": completed,
        "total": total,
        "errors": errors
    })
    
    return {
        "success": len(errors) == 0,
        "completed": completed,
        "total": total,
        "errors": errors
    }
