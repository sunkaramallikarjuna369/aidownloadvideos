from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional
import os
import json
import asyncio
import aiofiles
import requests
import time
import zipfile
import io
import shutil
import re
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import uuid

app = FastAPI()

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# In-memory storage for sessions and download progress
sessions = {}
download_progress = {}
download_tasks = {}

# Base download directory
DOWNLOAD_BASE_DIR = "/home/ubuntu/aidownloadvideos/downloads"
os.makedirs(DOWNLOAD_BASE_DIR, exist_ok=True)

class LoginRequest(BaseModel):
    course_url: str
    username: str
    password: str

class DownloadRequest(BaseModel):
    session_id: str
    module_ids: list[str]

class ModuleInfo(BaseModel):
    id: str
    name: str
    items: list[dict]

def get_chrome_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

def is_qpiai_explorer(url: str) -> bool:
    """Check if the URL is a QpiAI Explorer platform"""
    return "qpiai.tech" in url or "explorer" in url.lower()

def login_qpiai_explorer(driver, base_url: str, username: str, password: str) -> bool:
    """Login to QpiAI Explorer platform"""
    try:
        # Navigate to login page
        login_url = urljoin(base_url, "/auth/signin")
        driver.get(login_url)
        time.sleep(3)
        
        # Fill email
        email_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='email'], input[type='email']"))
        )
        email_field.clear()
        email_field.send_keys(username)
        
        # Fill password
        password_field = driver.find_element(By.CSS_SELECTOR, "input[name='password'], input[type='password']")
        password_field.clear()
        password_field.send_keys(password)
        
        # Click sign in button
        submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_btn.click()
        
        time.sleep(5)
        
        # Check if login was successful (should redirect away from signin page)
        return "/auth/signin" not in driver.current_url
        
    except Exception as e:
        print(f"QpiAI login error: {e}")
        return False

def scrape_qpiai_modules(driver, course_url: str) -> list:
    """Scrape modules from QpiAI Explorer platform"""
    modules = []
    
    try:
        # Navigate to modules page
        driver.get(course_url)
        time.sleep(3)
        
        # Wait for the modules table to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table, [class*='module'], [class*='lesson']"))
        )
        
        # Get page source and parse
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Find all module/lesson rows in the table
        rows = soup.select("tr, [class*='lesson-row'], [class*='module-item']")
        
        module_id = 0
        for row in rows:
            # Skip header rows
            if row.find('th'):
                continue
            
            # Get the title from the row
            title_elem = row.select_one("td:nth-child(2), [class*='title'], a")
            if title_elem:
                title = title_elem.get_text(strip=True)
                if title and len(title) > 2:
                    module_id += 1
                    
                    # Try to find a link to the lesson
                    link = row.find('a')
                    lesson_url = ""
                    if link and link.get('href'):
                        href = link.get('href')
                        lesson_url = href if href.startswith('http') else urljoin(course_url, href)
                    
                    modules.append({
                        "id": str(module_id),
                        "name": title,
                        "lesson_url": lesson_url,
                        "items": []
                    })
        
        # If no modules found from table, try clicking on each row to get video URLs
        if not modules:
            # Try alternative selectors for QpiAI
            lesson_elements = soup.select("[class*='curriculum'], [class*='lesson'], [class*='chapter']")
            for elem in lesson_elements:
                module_id += 1
                title = elem.get_text(strip=True)[:100]
                if title:
                    modules.append({
                        "id": str(module_id),
                        "name": title,
                        "lesson_url": "",
                        "items": []
                    })
        
        # Now navigate to each module to extract video URLs
        for module in modules:
            if module.get("lesson_url"):
                try:
                    driver.get(module["lesson_url"])
                    time.sleep(2)
                    
                    # Look for video elements
                    video_soup = BeautifulSoup(driver.page_source, 'html.parser')
                    
                    # Find video sources
                    video_sources = video_soup.select("video source, video[src], [data-video-url], iframe[src*='video'], iframe[src*='vimeo'], iframe[src*='youtube']")
                    for video in video_sources:
                        video_url = video.get('src') or video.get('data-video-url')
                        if video_url:
                            module["items"].append({
                                "type": "video",
                                "name": f"{module['name']} - Video",
                                "url": video_url if video_url.startswith('http') else urljoin(course_url, video_url)
                            })
                    
                    # Find PDF links
                    pdf_links = video_soup.select("a[href*='.pdf'], a[href*='pdf']")
                    for pdf in pdf_links:
                        pdf_url = pdf.get('href')
                        if pdf_url:
                            module["items"].append({
                                "type": "pdf",
                                "name": pdf.get_text(strip=True) or f"{module['name']} - PDF",
                                "url": pdf_url if pdf_url.startswith('http') else urljoin(course_url, pdf_url)
                            })
                    
                    # Check for downloadable resources
                    download_links = video_soup.select("a[download], a[href*='download']")
                    for link in download_links:
                        link_url = link.get('href')
                        if link_url:
                            module["items"].append({
                                "type": "file",
                                "name": link.get_text(strip=True) or "Resource",
                                "url": link_url if link_url.startswith('http') else urljoin(course_url, link_url)
                            })
                            
                except Exception as e:
                    print(f"Error scraping module {module['name']}: {e}")
        
        return modules
        
    except Exception as e:
        print(f"Error scraping QpiAI modules: {e}")
        return modules

@app.post("/api/login")
async def login(request: LoginRequest):
    """Login to the course platform and return session info with modules"""
    session_id = str(uuid.uuid4())
    
    try:
        driver = get_chrome_driver()
        
        # Check if this is QpiAI Explorer platform
        if is_qpiai_explorer(request.course_url):
            # Use QpiAI-specific login and scraping
            base_url = f"{urlparse(request.course_url).scheme}://{urlparse(request.course_url).netloc}"
            
            login_success = login_qpiai_explorer(driver, base_url, request.username, request.password)
            
            if login_success:
                # Scrape modules from QpiAI
                modules = scrape_qpiai_modules(driver, request.course_url)
                
                cookies = driver.get_cookies()
                current_url = driver.current_url
                page_source = driver.page_source
                
                # Store session info
                sessions[session_id] = {
                    "cookies": cookies,
                    "course_url": request.course_url,
                    "current_url": current_url,
                    "page_source": page_source,
                    "modules": modules,
                    "platform": "qpiai"
                }
                
                driver.quit()
                
                return {
                    "success": True,
                    "session_id": session_id,
                    "modules": modules,
                    "message": f"Found {len(modules)} modules from QpiAI Explorer"
                }
            else:
                driver.quit()
                return {
                    "success": False,
                    "error": "Login failed",
                    "message": "Failed to login to QpiAI Explorer. Please check your credentials."
                }
        
        # Generic login for other platforms
        driver.get(request.course_url)
        time.sleep(3)
        
        # Try to find and fill login form
        try:
            # Common login form selectors
            username_selectors = [
                "input[name='username']",
                "input[name='email']",
                "input[type='email']",
                "input[id='username']",
                "input[id='email']",
                "#login-email",
                "#email",
                "input[placeholder*='email' i]",
                "input[placeholder*='username' i]"
            ]
            
            password_selectors = [
                "input[name='password']",
                "input[type='password']",
                "input[id='password']",
                "#login-password",
                "#password"
            ]
            
            submit_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "button:contains('Login')",
                "button:contains('Sign in')",
                ".login-button",
                "#login-button",
                "button.btn-primary"
            ]
            
            username_field = None
            for selector in username_selectors:
                try:
                    username_field = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    break
                except:
                    continue
            
            if username_field:
                username_field.clear()
                username_field.send_keys(request.username)
            
            password_field = None
            for selector in password_selectors:
                try:
                    password_field = driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except:
                    continue
            
            if password_field:
                password_field.clear()
                password_field.send_keys(request.password)
            
            # Click submit button
            submit_button = None
            for selector in submit_selectors:
                try:
                    submit_button = driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except:
                    continue
            
            if submit_button:
                submit_button.click()
                time.sleep(5)
            
        except Exception as e:
            print(f"Login form interaction error: {e}")
        
        # Get page source after login
        page_source = driver.page_source
        current_url = driver.current_url
        cookies = driver.get_cookies()
        
        # Parse modules from the page
        modules = parse_modules_from_page(page_source, current_url)
        
        # Store session info
        sessions[session_id] = {
            "cookies": cookies,
            "course_url": request.course_url,
            "current_url": current_url,
            "page_source": page_source,
            "modules": modules
        }
        
        driver.quit()
        
        return {
            "success": True,
            "session_id": session_id,
            "modules": modules,
            "message": f"Found {len(modules)} modules"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to login or parse course content"
        }

def parse_modules_from_page(page_source: str, base_url: str) -> list:
    """Parse course modules from the page HTML"""
    soup = BeautifulSoup(page_source, 'html.parser')
    modules = []
    
    # Common module/section selectors for various LMS platforms
    module_selectors = [
        # Generic selectors
        ".module", ".section", ".chapter", ".lesson",
        "[class*='module']", "[class*='section']", "[class*='chapter']",
        ".course-module", ".course-section", ".course-chapter",
        # Specific LMS selectors
        ".curriculum-item", ".lecture-item", ".content-item",
        ".accordion-item", ".collapse-item",
        "li[class*='module']", "div[class*='module']",
        # Video/content containers
        ".video-item", ".pdf-item", ".resource-item",
        "[data-type='video']", "[data-type='pdf']"
    ]
    
    module_id = 0
    
    # Try to find modules using various selectors
    for selector in module_selectors:
        try:
            elements = soup.select(selector)
            for elem in elements:
                module_id += 1
                module_name = elem.get_text(strip=True)[:100] or f"Module {module_id}"
                
                # Find items within the module
                items = []
                
                # Look for video links
                video_links = elem.select("a[href*='video'], a[href*='.mp4'], video source, [data-video-url]")
                for video in video_links:
                    video_url = video.get('href') or video.get('src') or video.get('data-video-url')
                    if video_url:
                        items.append({
                            "type": "video",
                            "name": video.get_text(strip=True) or "Video",
                            "url": video_url if video_url.startswith('http') else base_url + video_url
                        })
                
                # Look for PDF links
                pdf_links = elem.select("a[href*='.pdf'], a[href*='pdf'], [data-pdf-url]")
                for pdf in pdf_links:
                    pdf_url = pdf.get('href') or pdf.get('data-pdf-url')
                    if pdf_url:
                        items.append({
                            "type": "pdf",
                            "name": pdf.get_text(strip=True) or "PDF Document",
                            "url": pdf_url if pdf_url.startswith('http') else base_url + pdf_url
                        })
                
                # Look for general downloadable links
                download_links = elem.select("a[download], a[href*='download']")
                for link in download_links:
                    link_url = link.get('href')
                    if link_url:
                        items.append({
                            "type": "file",
                            "name": link.get_text(strip=True) or "File",
                            "url": link_url if link_url.startswith('http') else base_url + link_url
                        })
                
                if module_name and len(module_name) > 2:
                    modules.append({
                        "id": str(module_id),
                        "name": module_name,
                        "items": items
                    })
        except Exception as e:
            continue
    
    # If no modules found, try to extract all links
    if not modules:
        all_links = soup.select("a[href]")
        video_items = []
        pdf_items = []
        
        for link in all_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            if any(ext in href.lower() for ext in ['.mp4', '.webm', '.mov', 'video']):
                video_items.append({
                    "type": "video",
                    "name": text or "Video",
                    "url": href if href.startswith('http') else base_url + href
                })
            elif '.pdf' in href.lower():
                pdf_items.append({
                    "type": "pdf",
                    "name": text or "PDF",
                    "url": href if href.startswith('http') else base_url + href
                })
        
        if video_items or pdf_items:
            modules.append({
                "id": "1",
                "name": "Course Content",
                "items": video_items + pdf_items
            })
    
    return modules

@app.post("/api/scan-page")
async def scan_page(request: LoginRequest):
    """Scan a page for downloadable content without full login"""
    try:
        driver = get_chrome_driver()
        driver.get(request.course_url)
        time.sleep(3)
        
        # Try login if credentials provided
        if request.username and request.password:
            try:
                # Find and fill login form
                username_selectors = [
                    "input[name='username']", "input[name='email']", 
                    "input[type='email']", "input[id='username']",
                    "input[id='email']", "#email"
                ]
                password_selectors = [
                    "input[name='password']", "input[type='password']",
                    "input[id='password']", "#password"
                ]
                
                for selector in username_selectors:
                    try:
                        elem = driver.find_element(By.CSS_SELECTOR, selector)
                        elem.send_keys(request.username)
                        break
                    except:
                        continue
                
                for selector in password_selectors:
                    try:
                        elem = driver.find_element(By.CSS_SELECTOR, selector)
                        elem.send_keys(request.password)
                        break
                    except:
                        continue
                
                # Try to submit
                submit_selectors = ["button[type='submit']", "input[type='submit']", ".btn-primary"]
                for selector in submit_selectors:
                    try:
                        elem = driver.find_element(By.CSS_SELECTOR, selector)
                        elem.click()
                        time.sleep(5)
                        break
                    except:
                        continue
                        
            except Exception as e:
                print(f"Login attempt error: {e}")
        
        page_source = driver.page_source
        current_url = driver.current_url
        cookies = driver.get_cookies()
        
        # Parse content
        modules = parse_modules_from_page(page_source, current_url)
        
        session_id = str(uuid.uuid4())
        sessions[session_id] = {
            "cookies": cookies,
            "course_url": request.course_url,
            "current_url": current_url,
            "page_source": page_source,
            "modules": modules
        }
        
        driver.quit()
        
        return {
            "success": True,
            "session_id": session_id,
            "modules": modules,
            "current_url": current_url,
            "page_title": BeautifulSoup(page_source, 'html.parser').title.string if BeautifulSoup(page_source, 'html.parser').title else "Course"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/api/download")
async def start_download(request: DownloadRequest, background_tasks: BackgroundTasks):
    """Start downloading selected modules"""
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[request.session_id]
    download_id = str(uuid.uuid4())
    
    # Create download directory
    download_dir = os.path.join(DOWNLOAD_BASE_DIR, download_id)
    os.makedirs(download_dir, exist_ok=True)
    
    # Initialize progress
    download_progress[download_id] = {
        "status": "starting",
        "total_items": 0,
        "completed_items": 0,
        "current_item": "",
        "errors": [],
        "downloaded_files": []
    }
    
    # Start background download
    background_tasks.add_task(
        download_modules_task,
        download_id,
        session,
        request.module_ids,
        download_dir
    )
    
    return {
        "download_id": download_id,
        "message": "Download started"
    }

async def download_modules_task(download_id: str, session: dict, module_ids: list, download_dir: str):
    """Background task to download modules"""
    try:
        modules = session.get("modules", [])
        cookies = session.get("cookies", [])
        
        # Filter selected modules
        selected_modules = [m for m in modules if m["id"] in module_ids] if module_ids else modules
        
        # Count total items
        total_items = sum(len(m.get("items", [])) for m in selected_modules)
        download_progress[download_id]["total_items"] = total_items
        download_progress[download_id]["status"] = "downloading"
        
        # Create requests session with cookies
        req_session = requests.Session()
        for cookie in cookies:
            req_session.cookies.set(cookie['name'], cookie['value'])
        
        completed = 0
        
        for module in selected_modules:
            module_name = sanitize_filename(module["name"])
            module_dir = os.path.join(download_dir, module_name)
            os.makedirs(module_dir, exist_ok=True)
            
            for item in module.get("items", []):
                try:
                    item_name = sanitize_filename(item.get("name", "file"))
                    item_url = item.get("url", "")
                    item_type = item.get("type", "file")
                    
                    download_progress[download_id]["current_item"] = f"{module_name}/{item_name}"
                    
                    if item_url:
                        # Determine file extension
                        if item_type == "video":
                            ext = ".mp4" if ".mp4" not in item_name.lower() else ""
                        elif item_type == "pdf":
                            ext = ".pdf" if ".pdf" not in item_name.lower() else ""
                        else:
                            ext = ""
                        
                        file_path = os.path.join(module_dir, f"{item_name}{ext}")
                        
                        # Download file
                        response = req_session.get(item_url, stream=True, timeout=300)
                        if response.status_code == 200:
                            with open(file_path, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=8192):
                                    f.write(chunk)
                            
                            download_progress[download_id]["downloaded_files"].append({
                                "module": module_name,
                                "file": item_name,
                                "path": file_path,
                                "type": item_type
                            })
                        else:
                            download_progress[download_id]["errors"].append(
                                f"Failed to download {item_name}: HTTP {response.status_code}"
                            )
                    
                    completed += 1
                    download_progress[download_id]["completed_items"] = completed
                    
                except Exception as e:
                    download_progress[download_id]["errors"].append(f"Error downloading {item.get('name', 'file')}: {str(e)}")
                    completed += 1
                    download_progress[download_id]["completed_items"] = completed
        
        download_progress[download_id]["status"] = "completed"
        download_progress[download_id]["download_dir"] = download_dir
        
    except Exception as e:
        download_progress[download_id]["status"] = "error"
        download_progress[download_id]["errors"].append(str(e))

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to remove invalid characters"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename[:100]  # Limit length

@app.get("/api/download/progress/{download_id}")
async def get_download_progress(download_id: str):
    """Get download progress"""
    if download_id not in download_progress:
        raise HTTPException(status_code=404, detail="Download not found")
    
    return download_progress[download_id]

@app.get("/api/download/zip/{download_id}")
async def download_zip(download_id: str):
    """Download all files as a ZIP"""
    if download_id not in download_progress:
        raise HTTPException(status_code=404, detail="Download not found")
    
    progress = download_progress[download_id]
    if progress["status"] != "completed":
        raise HTTPException(status_code=400, detail="Download not yet completed")
    
    download_dir = progress.get("download_dir")
    if not download_dir or not os.path.exists(download_dir):
        raise HTTPException(status_code=404, detail="Download directory not found")
    
    # Create ZIP file
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(download_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arc_name = os.path.relpath(file_path, download_dir)
                zip_file.write(file_path, arc_name)
    
    zip_buffer.seek(0)
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=course_content_{download_id[:8]}.zip"}
    )

@app.get("/api/sessions")
async def list_sessions():
    """List all active sessions"""
    return {
        "sessions": [
            {
                "session_id": sid,
                "course_url": data.get("course_url"),
                "module_count": len(data.get("modules", []))
            }
            for sid, data in sessions.items()
        ]
    }

@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session"""
    if session_id in sessions:
        del sessions[session_id]
        return {"message": "Session deleted"}
    raise HTTPException(status_code=404, detail="Session not found")

@app.get("/api/downloads")
async def list_downloads():
    """List all downloads"""
    return {
        "downloads": [
            {
                "download_id": did,
                "status": data.get("status"),
                "completed": data.get("completed_items", 0),
                "total": data.get("total_items", 0)
            }
            for did, data in download_progress.items()
        ]
    }
