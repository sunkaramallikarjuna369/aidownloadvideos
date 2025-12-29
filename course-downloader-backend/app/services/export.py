"""
Export services for saving video URLs to files.
"""
import os
import json
import time
from typing import List, Dict, Any

from app.core.config import DEFAULT_DOWNLOAD_DIR


def save_videos_to_files(
    videos: List[Dict[str, Any]], 
    output_dir: str = None,
    course_url: str = "",
    total_lessons: int = 0
) -> Dict[str, str]:
    """
    Save video URLs to JSON, CSV, and TXT files.
    
    Args:
        videos: List of video dictionaries with module, chapter, title, url
        output_dir: Directory to save files (defaults to DOWNLOAD_BASE_DIR)
        course_url: Original course URL for metadata
        total_lessons: Total number of lessons for metadata
        
    Returns:
        Dictionary with paths to saved files
    """
    output_dir = output_dir or DEFAULT_DOWNLOAD_DIR
    os.makedirs(output_dir, exist_ok=True)
    
    # Save as JSON
    json_file = os.path.join(output_dir, "video_urls.json")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump({
            "course_url": course_url,
            "total_videos": len(videos),
            "total_lessons": total_lessons,
            "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "videos": videos
        }, f, indent=2, ensure_ascii=False)
    print(f"Saved video URLs to: {json_file}")
    
    # Save as CSV for easy viewing
    csv_file = os.path.join(output_dir, "video_urls.csv")
    with open(csv_file, 'w', encoding='utf-8') as f:
        f.write("Module,Chapter,Title,URL\n")
        for video in videos:
            # Escape commas and quotes in fields
            module = video.get('module', '').replace('"', '""')
            chapter = video.get('chapter', '').replace('"', '""')
            title = video.get('title', '').replace('"', '""')
            url = video.get('url', '')
            f.write(f'"{module}","{chapter}","{title}","{url}"\n')
    print(f"Saved video URLs to: {csv_file}")
    
    # Save as simple text file with just URLs
    txt_file = os.path.join(output_dir, "video_urls.txt")
    with open(txt_file, 'w', encoding='utf-8') as f:
        for video in videos:
            f.write(f"{video.get('url', '')}\n")
    print(f"Saved video URLs to: {txt_file}")
    
    return {
        "json": json_file,
        "csv": csv_file,
        "txt": txt_file
    }


def save_course_structure(
    lessons: List[Dict[str, Any]],
    output_dir: str = None,
    total_modules: int = 0
) -> str:
    """
    Save course structure to JSON file.
    
    Args:
        lessons: List of lesson dictionaries
        output_dir: Directory to save file
        total_modules: Total number of modules
        
    Returns:
        Path to saved file
    """
    output_dir = output_dir or DEFAULT_DOWNLOAD_DIR
    os.makedirs(output_dir, exist_ok=True)
    
    json_file = os.path.join(output_dir, "course_structure.json")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump({
            "total_modules": total_modules,
            "total_lessons": len(lessons),
            "lessons": lessons
        }, f, indent=2, ensure_ascii=False)
    
    print(f"Saved course structure to: {json_file}")
    return json_file
