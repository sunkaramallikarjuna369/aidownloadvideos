"""
Configuration settings for the course downloader application.
"""
import os
from pathlib import Path

# Base download directory - can be overridden by user
DEFAULT_DOWNLOAD_DIR = os.environ.get(
    "DOWNLOAD_DIR", 
    str(Path(__file__).parent.parent.parent.parent / "downloads")
)

# Ensure download directory exists
os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)

# User agent for HTTP requests
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# QpiAI API endpoints
QPIAI_API_BASE = "https://server-explorer-dev.qpiai.tech/api"
QPIAI_COURSES_API = f"{QPIAI_API_BASE}/courses"
QPIAI_MODULES_API = f"{QPIAI_API_BASE}/modules"
QPIAI_CHAPTERS_API = f"{QPIAI_API_BASE}/chapters"

# Selenium settings
SELENIUM_TIMEOUT = 10
SELENIUM_PAGE_LOAD_WAIT = 5

# Download settings
MAX_CONCURRENT_DOWNLOADS = 3
DOWNLOAD_CHUNK_SIZE = 8192
DOWNLOAD_RETRY_COUNT = 3
