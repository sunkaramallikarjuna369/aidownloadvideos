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
    download_path: str = ""  # Optional custom download path

class ModuleInfo(BaseModel):
    id: str
    name: str
    items: list[dict]

def get_chrome_driver(enable_network_logging=False):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Enable network logging for video URL detection (like browser extensions)
    if enable_network_logging:
        chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

# Store user agent for download requests
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

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

def detect_video_urls_from_page(driver, base_url: str) -> list:
    """
    Detect video URLs from a page like browser video downloader extensions do.
    This uses JavaScript execution to find all video sources including dynamically loaded ones.
    """
    video_urls = []
    
    # JavaScript to find all video sources on the page
    js_find_videos = """
    var videos = [];
    
    // Find all video elements
    document.querySelectorAll('video').forEach(function(video) {
        if (video.src && video.src.length > 0) {
            videos.push({type: 'video', src: video.src});
        }
        if (video.currentSrc && video.currentSrc.length > 0) {
            videos.push({type: 'video', src: video.currentSrc});
        }
        // Check source elements inside video
        video.querySelectorAll('source').forEach(function(source) {
            if (source.src && source.src.length > 0) {
                videos.push({type: 'video', src: source.src});
            }
        });
    });
    
    // Find video iframes (YouTube, Vimeo, etc.)
    document.querySelectorAll('iframe').forEach(function(iframe) {
        var src = iframe.src || '';
        if (src.includes('youtube') || src.includes('vimeo') || src.includes('video') || src.includes('player')) {
            videos.push({type: 'iframe', src: src});
        }
    });
    
    // Find elements with video data attributes
    document.querySelectorAll('[data-video-url], [data-src], [data-video], [data-video-src]').forEach(function(el) {
        var url = el.getAttribute('data-video-url') || el.getAttribute('data-src') || 
                  el.getAttribute('data-video') || el.getAttribute('data-video-src');
        if (url && url.length > 0) {
            videos.push({type: 'data-attr', src: url});
        }
    });
    
    // Find video URLs in script tags (common for video players)
    document.querySelectorAll('script').forEach(function(script) {
        var content = script.textContent || '';
        // Look for common video URL patterns
        var patterns = [
            /["']([^"']*\\.mp4[^"']*)["']/gi,
            /["']([^"']*\\.webm[^"']*)["']/gi,
            /["']([^"']*\\.m3u8[^"']*)["']/gi,
            /["'](https?:\\/\\/[^"']*video[^"']*)["']/gi,
            /videoUrl["']?\\s*[:=]\\s*["']([^"']+)["']/gi,
            /src["']?\\s*[:=]\\s*["']([^"']*\\.(mp4|webm|m3u8)[^"']*)["']/gi
        ];
        patterns.forEach(function(pattern) {
            var matches = content.match(pattern);
            if (matches) {
                matches.forEach(function(match) {
                    // Extract URL from the match
                    var urlMatch = match.match(/["']([^"']+)["']/);
                    if (urlMatch && urlMatch[1]) {
                        videos.push({type: 'script', src: urlMatch[1]});
                    }
                });
            }
        });
    });
    
    // Find object/embed elements
    document.querySelectorAll('object, embed').forEach(function(el) {
        var src = el.getAttribute('data') || el.getAttribute('src');
        if (src && (src.includes('video') || src.includes('.mp4') || src.includes('.webm'))) {
            videos.push({type: 'embed', src: src});
        }
    });
    
    return videos;
    """
    
    try:
        # Execute JavaScript to find videos
        found_videos = driver.execute_script(js_find_videos)
        
        seen_urls = set()
        for video in found_videos:
            src = video.get('src', '')
            if src and src not in seen_urls and not src.startswith('blob:'):
                # Make URL absolute if needed
                if not src.startswith('http'):
                    src = urljoin(base_url, src)
                seen_urls.add(src)
                video_urls.append({
                    "type": video.get('type', 'video'),
                    "url": src
                })
        
        # Also check page source for video URLs that JS might miss
        page_source = driver.page_source
        
        # Common video URL patterns
        video_patterns = [
            r'https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*',
            r'https?://[^\s"\'<>]+\.webm[^\s"\'<>]*',
            r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*',
            r'https?://[^\s"\'<>]*cloudfront[^\s"\'<>]*video[^\s"\'<>]*',
            r'https?://[^\s"\'<>]*s3[^\s"\'<>]*\.mp4[^\s"\'<>]*',
        ]
        
        for pattern in video_patterns:
            matches = re.findall(pattern, page_source, re.IGNORECASE)
            for match in matches:
                # Clean up the URL
                clean_url = match.rstrip('\\').rstrip('"').rstrip("'")
                if clean_url not in seen_urls:
                    seen_urls.add(clean_url)
                    video_urls.append({
                        "type": "regex",
                        "url": clean_url
                    })
        
    except Exception as e:
        print(f"Error detecting videos: {e}")
    
    return video_urls

def scrape_qpiai_modules(driver, course_url: str) -> list:
    """Scrape modules from QpiAI Explorer platform
    
    Based on actual site analysis (Dec 2025):
    
    Site Structure:
    - Modules page (/modules) has a dropdown to select module categories
    - When "All Modules" is selected, table shows module names without links
    - When a specific module is selected, table shows lessons WITH clickable links
    - Each lesson page has a "Browse Lessons" button that opens a sidebar
    - The sidebar shows ALL modules > chapters > lessons in a hierarchical tree
    
    Strategy:
    1. Navigate to modules page
    2. Wait for table to load (look for "S.No" header)
    3. If table has links, extract lessons from table
    4. If no links, click first lesson to access "Browse Lessons" sidebar
    5. From sidebar, expand all modules and extract all lesson links
    """
    modules = []
    seen_titles = set()  # Track seen titles to avoid duplicates
    module_id = 0
    
    try:
        # Navigate to course page
        print(f"Navigating to: {course_url}")
        driver.get(course_url)
        time.sleep(5)  # Wait for SPA to load
        
        # Log current URL after navigation
        current_url = driver.current_url
        print(f"Current URL after navigation: {current_url}")
        
        # First, click on "Modules" in the left sidebar to get to the modules list
        print("Step 1: Clicking on 'Modules' in left sidebar...")
        try:
            time.sleep(2)
            modules_selectors = [
                "//a[contains(text(), 'Modules')]",
                "//*[contains(text(), 'Modules') and (self::button or self::a or self::div or self::span)]",
                "//nav//a[contains(., 'Modules')]",
                "a[href*='modules']",
            ]
            
            clicked = False
            for selector in modules_selectors:
                try:
                    if selector.startswith("//"):
                        elem = driver.find_element(By.XPATH, selector)
                    else:
                        elem = driver.find_element(By.CSS_SELECTOR, selector)
                    if elem.is_displayed():
                        elem.click()
                        clicked = True
                        print(f"Clicked Modules using: {selector}")
                        break
                except:
                    continue
            
            if clicked:
                time.sleep(3)
                print(f"Now at: {driver.current_url}")
        except Exception as e:
            print(f"Error clicking Modules: {e}")
        
        # Step 1.5: Wait for table to load and check if we need to select a specific module
        print("\nStep 1.5: Checking if we need to select a specific module from dropdown...")
        time.sleep(2)
        
        # Check if table rows have links (if "All Modules" is selected, they won't have links)
        table_links = driver.find_elements(By.CSS_SELECTOR, "table tbody tr td a")
        print(f"Found {len(table_links)} links in table")
        
        if len(table_links) == 0:
            # Need to select a specific module from dropdown
            print("No links in table - need to select a specific module from dropdown")
            try:
                # Click on the module dropdown - use XPath for more precise targeting
                # Note: button:has(svg) doesn't work in Selenium, so we use XPath
                dropdown_clicked = False
                
                # Try XPath first - more reliable for finding the "All Modules" dropdown
                try:
                    all_modules_btn = driver.find_element(By.XPATH, "//button[contains(., 'All Modules')]")
                    if all_modules_btn.is_displayed():
                        all_modules_btn.click()
                        dropdown_clicked = True
                        print("Clicked 'All Modules' dropdown via XPath")
                        time.sleep(1)
                except:
                    pass
                
                # Fallback: try CSS selectors
                if not dropdown_clicked:
                    dropdown_selectors = [
                        "button[aria-expanded]",
                        "[role='combobox']",
                    ]
                    
                    for selector in dropdown_selectors:
                        try:
                            dropdowns = driver.find_elements(By.CSS_SELECTOR, selector)
                            for dropdown in dropdowns:
                                text = dropdown.text.strip()
                                if 'All Modules' in text or 'Prerequisites' in text or 'Quantum' in text:
                                    dropdown.click()
                                    dropdown_clicked = True
                                    print(f"Clicked dropdown: {text}")
                                    time.sleep(1)
                                    break
                            if dropdown_clicked:
                                break
                        except:
                            continue
                
                # Now select "Prerequisites for Quantum Computing" from the dropdown options
                if dropdown_clicked:
                    time.sleep(1)
                    options = driver.find_elements(By.CSS_SELECTOR, "[role='option'], [aria-selected]")
                    for opt in options:
                        opt_text = opt.text.strip()
                        if 'Prerequisites' in opt_text and 'All' not in opt_text:
                            opt.click()
                            print(f"Selected module: {opt_text}")
                            time.sleep(2)
                            break
            except Exception as e:
                print(f"Error selecting module from dropdown: {e}")
        
        # Step 2: Click on the first lesson in the table to access the "Explore Course Content" sidebar
        print("\nStep 2: Clicking on first lesson to access 'Explore Course Content' sidebar...")
        try:
            # Wait for table to load
            time.sleep(2)
            
            # Find and click the first lesson row/link
            first_lesson_selectors = [
                "table tbody tr td a",  # Link in table cell
                "table tbody tr:first-child",  # First table row
                "[role='row'] a",  # Link in row
                "a[href*='lessons']",  # Any lesson link
                "a[href*='chapters']",  # Any chapter link
            ]
            
            clicked_lesson = False
            for selector in first_lesson_selectors:
                try:
                    elems = driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elems:
                        if elem.is_displayed():
                            elem.click()
                            clicked_lesson = True
                            print(f"Clicked first lesson using: {selector}")
                            break
                    if clicked_lesson:
                        break
                except:
                    continue
            
            if clicked_lesson:
                time.sleep(4)  # Wait for lesson page to load
                print(f"Now at lesson page: {driver.current_url}")
            else:
                print("Could not click on first lesson")
        except Exception as e:
            print(f"Error clicking first lesson: {e}")
        
        # Step 3: Find and interact with the "Explore Course Content" sidebar
        print("\nStep 3: Looking for 'Explore Course Content' sidebar...")
        
        # The sidebar might need to be opened via a button
        try:
            # Look for "Explore" or "Browse" button to open the sidebar
            explore_buttons = [
                "//*[contains(text(), 'Explore Course Content')]",
                "//*[contains(text(), 'Browse')]",
                "//*[contains(text(), 'Explore')]",
                "button[aria-label*='explore']",
                "button[aria-label*='browse']",
            ]
            
            for selector in explore_buttons:
                try:
                    if selector.startswith("//"):
                        btn = driver.find_element(By.XPATH, selector)
                    else:
                        btn = driver.find_element(By.CSS_SELECTOR, selector)
                    if btn.is_displayed():
                        # Check if it's a button that needs clicking
                        if btn.tag_name == 'button':
                            btn.click()
                            print(f"Clicked explore button: {selector}")
                            time.sleep(2)
                        break
                except:
                    continue
        except Exception as e:
            print(f"Note: {e}")
        
        # Step 4: Extract sections and lessons from the sidebar
        print("\nStep 4: Extracting sections and lessons from sidebar...")
        
        # Find all section headers (expandable accordion items)
        section_selectors = [
            # Accordion/expandable sections
            "[aria-expanded]",
            "button[aria-expanded]",
            "[role='button'][aria-expanded]",
            # Common patterns for course content sidebars
            "[class*='accordion'] > div",
            "[class*='chapter']",
            "[class*='section']",
            "[class*='module']",
        ]
        
        sections_found = []
        
        for selector in section_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                print(f"Selector '{selector}' found {len(elements)} elements")
                
                for elem in elements:
                    try:
                        text = elem.text.strip()
                        if text and len(text) > 3 and text not in seen_titles:
                            # Check if this looks like a section header
                            if any(keyword in text.lower() for keyword in ['quantum', 'linear', 'algebra', 'mechanics', 'computer', 'prerequisites', 'introduction', 'basics', 'essential', 'part']):
                                sections_found.append({
                                    'text': text.split('\n')[0],  # First line only
                                    'element': elem,
                                    'expanded': elem.get_attribute('aria-expanded') == 'true'
                                })
                                seen_titles.add(text)
                    except:
                        continue
            except Exception as e:
                print(f"Selector '{selector}' error: {e}")
        
        print(f"Found {len(sections_found)} potential sections")
        
        # Step 5: Find all lesson links - SCOPED TO SIDEBAR ONLY
        # IMPORTANT: We must scope to the "Explore Course Content" sidebar to avoid
        # capturing "Next"/"Previous" navigation links from the lesson page
        print("\nStep 5: Finding all lesson links (scoped to sidebar)...")
        
        lesson_links = []
        
        # First, try to find the sidebar container
        sidebar_container = None
        sidebar_selectors = [
            "//h2[contains(text(), 'Explore Course Content')]/parent::div/parent::div",
            "//h2[contains(text(), 'Explore Course Content')]/ancestor::div[contains(@tabindex, '-1')]",
            "[tabindex='-1']:has(h2)",  # Fallback - dialog containers
        ]
        
        for selector in sidebar_selectors:
            try:
                if selector.startswith("//"):
                    sidebar_container = driver.find_element(By.XPATH, selector)
                else:
                    # CSS :has() doesn't work in Selenium, skip it
                    if ':has(' in selector:
                        continue
                    sidebar_container = driver.find_element(By.CSS_SELECTOR, selector)
                if sidebar_container:
                    print(f"Found sidebar container using: {selector}")
                    break
            except:
                continue
        
        # If we found the sidebar, search within it; otherwise search the whole page
        search_context = sidebar_container if sidebar_container else driver
        context_name = "sidebar" if sidebar_container else "whole page"
        print(f"Searching for lesson links in: {context_name}")
        
        # Navigation links to filter out
        nav_link_texts = {'next', 'previous', 'prev', '←', '→', '<', '>'}
        
        lesson_selectors = [
            "a[href*='/lessons/']",
        ]
        
        for selector in lesson_selectors:
            try:
                links = search_context.find_elements(By.CSS_SELECTOR, selector)
                print(f"Selector '{selector}' found {len(links)} links in {context_name}")
                
                for link in links:
                    try:
                        href = link.get_attribute('href')
                        text = link.text.strip()
                        
                        # Filter out navigation links (Next/Previous)
                        if text.lower() in nav_link_texts:
                            print(f"  Skipping navigation link: {text}")
                            continue
                        
                        # Filter out empty or very short text
                        if not text or len(text) < 3:
                            continue
                        
                        if href and '/lessons/' in href:
                            if text not in seen_titles:
                                seen_titles.add(text)
                                lesson_links.append({
                                    'name': text,
                                    'url': href
                                })
                                print(f"  Found lesson: {text[:50]}...")
                    except:
                        continue
            except Exception as e:
                print(f"Selector '{selector}' error: {e}")
        
        print(f"Found {len(lesson_links)} lesson links")
        
        # Step 6: If we found lesson links, create modules from them
        if lesson_links:
            print("\nStep 6: Creating modules from lesson links...")
            for lesson in lesson_links:
                module_id += 1
                modules.append({
                    "id": str(module_id),
                    "name": lesson['name'],
                    "lesson_url": lesson['url'],
                    "status": "Not Started",
                    "items": []
                })
                print(f"  Added module: {lesson['name']}")
        
        # Step 7: If no lesson links found, try expanding sections and finding lessons
        if not modules:
            print("\nStep 7: Trying to expand sections and find lessons...")
            
            # Try clicking on expandable sections
            try:
                expandable = driver.find_elements(By.CSS_SELECTOR, "[aria-expanded='false']")
                print(f"Found {len(expandable)} collapsed sections")
                
                for exp in expandable[:10]:  # Limit to first 10
                    try:
                        exp.click()
                        time.sleep(1)
                    except:
                        continue
                
                # Now look for lesson links again
                time.sleep(2)
                links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/lessons/']")
                print(f"After expanding, found {len(links)} lesson links")
                
                for link in links:
                    try:
                        href = link.get_attribute('href')
                        text = link.text.strip()
                        
                        if href and text and text not in seen_titles:
                            seen_titles.add(text)
                            module_id += 1
                            modules.append({
                                "id": str(module_id),
                                "name": text,
                                "lesson_url": href,
                                "status": "Not Started",
                                "items": []
                            })
                            print(f"  Added module: {text}")
                    except:
                        continue
            except Exception as e:
                print(f"Error expanding sections: {e}")
        
        # Fallback: Use the old table-based approach if sidebar approach didn't work
        if not modules:
            print("\nFallback: Using table-based approach...")
        
        # Additional wait for table rows to render
        time.sleep(2)
        
        # Save page source for debugging
        page_source = driver.page_source
        print(f"Page source length: {len(page_source)}")
        
        # Debug: Save page source to file for inspection
        import tempfile
        try:
            debug_file = os.path.join(tempfile.gettempdir(), f"qpiai_debug_{int(time.time())}.html")
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(page_source)
            print(f"Saved debug HTML to: {debug_file}")
        except Exception as e:
            print(f"Could not save debug file: {e}")
        
        # Check if we're logged in
        if "signin" in current_url.lower() or "login" in current_url.lower():
            print("ERROR: Still on login page - authentication may have failed!")
            return modules
        
        # Log element counts for debugging
        print("\n=== PAGE ELEMENT COUNTS ===")
        element_checks = [
            ("tables", "table"),
            ("tbody", "tbody"),
            ("table rows (tr)", "tr"),
            ("table cells (td)", "td"),
            ("divs with role=row", "[role='row']"),
            ("divs with role=grid", "[role='grid']"),
            ("divs with role=cell", "[role='cell']"),
            ("MuiTableRow", "[class*='MuiTableRow']"),
            ("MuiTableCell", "[class*='MuiTableCell']"),
            ("links (a)", "a"),
            ("buttons", "button"),
        ]
        for name, selector in element_checks:
            try:
                count = len(driver.find_elements(By.CSS_SELECTOR, selector))
                print(f"  {name}: {count}")
            except:
                print(f"  {name}: error")
        print("===========================\n")
        
        def extract_modules_from_current_page():
            """Extract module titles from the currently visible table/grid"""
            nonlocal module_id
            found_on_page = []
            
            # Strategy 1: Try standard HTML table with tbody
            try:
                rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                print(f"Strategy 1 (table tbody tr): Found {len(rows)} rows")
                
                for row in rows:
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) >= 2:
                            # S.No is first cell, Title is second cell
                            title = cells[1].text.strip()
                            status = cells[2].text.strip() if len(cells) >= 3 else ""
                            
                            if title and len(title) > 3 and title not in seen_titles:
                                # Skip header-like text
                                if title.lower() in ['title', 's.no', 'completion status']:
                                    continue
                                
                                # Skip course summary rows (contain "Lessons:" or "Assessments:")
                                # These are course-level rows, not individual lesson rows
                                if 'Lessons:' in title or 'Assessments:' in title or 'lessons:' in title.lower():
                                    print(f"  Skipping course summary row: {title[:50]}...")
                                    continue
                                    
                                seen_titles.add(title)
                                module_id += 1
                                
                                # Try to get the row's click URL by clicking and capturing
                                lesson_url = ""
                                try:
                                    link = row.find_element(By.TAG_NAME, "a")
                                    lesson_url = link.get_attribute("href") or ""
                                except:
                                    pass
                                
                                found_on_page.append({
                                    "id": str(module_id),
                                    "name": title,
                                    "lesson_url": lesson_url,
                                    "status": status,
                                    "items": [],
                                    "row_element": row  # Keep reference for clicking later
                                })
                                print(f"  Found module: {title}")
                    except StaleElementReferenceException:
                        continue
                    except Exception as e:
                        print(f"  Error parsing row: {e}")
            except Exception as e:
                print(f"Strategy 1 failed: {e}")
            
            # Strategy 2: Try MUI table rows if Strategy 1 found nothing
            if not found_on_page:
                try:
                    rows = driver.find_elements(By.CSS_SELECTOR, "[class*='MuiTableRow'], [role='row']")
                    print(f"Strategy 2 (MuiTableRow/role=row): Found {len(rows)} rows")
                    
                    for row in rows:
                        try:
                            cells = row.find_elements(By.CSS_SELECTOR, "[class*='MuiTableCell'], [role='cell'], td")
                            row_text = row.text.strip()
                            
                            if len(cells) >= 2:
                                title = cells[1].text.strip()
                                status = cells[2].text.strip() if len(cells) >= 3 else ""
                            elif row_text:
                                # Parse from row text (format: "1\nTitle\nStatus")
                                parts = row_text.split('\n')
                                if len(parts) >= 2:
                                    title = parts[1].strip()
                                    status = parts[2].strip() if len(parts) >= 3 else ""
                                else:
                                    continue
                            else:
                                continue
                            
                            if title and len(title) > 3 and title not in seen_titles:
                                if title.lower() in ['title', 's.no', 'completion status']:
                                    continue
                                
                                # Skip course summary rows (contain "Lessons:" or "Assessments:")
                                if 'Lessons:' in title or 'Assessments:' in title or 'lessons:' in title.lower():
                                    print(f"  Skipping course summary row: {title[:50]}...")
                                    continue
                                    
                                seen_titles.add(title)
                                module_id += 1
                                
                                lesson_url = ""
                                try:
                                    link = row.find_element(By.TAG_NAME, "a")
                                    lesson_url = link.get_attribute("href") or ""
                                except:
                                    pass
                                
                                found_on_page.append({
                                    "id": str(module_id),
                                    "name": title,
                                    "lesson_url": lesson_url,
                                    "status": status,
                                    "items": [],
                                    "row_element": row
                                })
                                print(f"  Found module: {title}")
                        except StaleElementReferenceException:
                            continue
                except Exception as e:
                    print(f"Strategy 2 failed: {e}")
            
            return found_on_page
        
        def go_to_next_page():
            """Click the next page button if available. Returns True if successful."""
            try:
                # Look for next page button (usually > or >> icon)
                next_buttons = driver.find_elements(By.CSS_SELECTOR, 
                    "button[aria-label*='next'], button[aria-label*='Next'], "
                    "[class*='pagination'] button:last-child, "
                    "button[title*='next'], button[title*='Next'], "
                    "[class*='MuiTablePagination'] button:nth-last-child(2)")
                
                for btn in next_buttons:
                    if btn.is_enabled() and btn.is_displayed():
                        # Check if it's not disabled
                        disabled = btn.get_attribute("disabled")
                        if disabled:
                            continue
                        btn.click()
                        time.sleep(2)  # Wait for page to load
                        return True
                return False
            except Exception as e:
                print(f"Error navigating to next page: {e}")
                return False
        
        # Extract modules from current page
        print("\n=== Extracting modules from page 1 ===")
        page_modules = extract_modules_from_current_page()
        modules.extend(page_modules)
        
        # Try to go to next page and extract more modules
        page_num = 1
        while page_num < 5:  # Safety limit
            print(f"\n=== Trying to go to page {page_num + 1} ===")
            if go_to_next_page():
                page_num += 1
                time.sleep(2)
                page_modules = extract_modules_from_current_page()
                if not page_modules:
                    print("No new modules found on this page")
                    break
                modules.extend(page_modules)
            else:
                print("No more pages available")
                break
        
        # If no modules found from table, try using Selenium to find clickable rows
        if not modules:
            print("No modules found from HTML table, trying Selenium selectors...")
            try:
                # Try finding rows directly with Selenium - multiple selector strategies
                selectors_to_try = [
                    "table tbody tr",
                    "tr[class*='row']",
                    "[role='row']",
                    "[role='grid'] [role='row']",
                    "[class*='MuiTableRow']",
                    "[class*='table'] [class*='row']",
                    "[data-testid*='row']",
                    "div[class*='list'] > div",
                    "[class*='module-item']",
                    "[class*='lesson-item']",
                    "[class*='content-item']",
                ]
                
                for selector in selectors_to_try:
                    if modules:
                        break
                    try:
                        table_rows = driver.find_elements(By.CSS_SELECTOR, selector)
                        print(f"Selector '{selector}' found {len(table_rows)} elements")
                        
                        for row in table_rows:
                            try:
                                # Try to get text from cells or child elements
                                cells = row.find_elements(By.CSS_SELECTOR, "td, [role='cell'], [class*='cell'], > div")
                                row_text = row.text.strip()
                                
                                title = ""
                                if len(cells) >= 2:
                                    title = cells[1].text.strip() if len(cells) > 1 else cells[0].text.strip()
                                elif row_text:
                                    # Use the row text if no cells found
                                    title = row_text.split('\n')[0].strip()
                                
                                if title and len(title) > 2 and not title.lower().startswith('s.no') and title.lower() != 'title':
                                    # Check if already exists
                                    existing = [m for m in modules if m['name'] == title]
                                    if not existing:
                                        module_id += 1
                                        
                                        # Try to find a link
                                        links = row.find_elements(By.TAG_NAME, "a")
                                        lesson_url = links[0].get_attribute('href') if links else ""
                                        
                                        modules.append({
                                            "id": str(module_id),
                                            "name": title,
                                            "lesson_url": lesson_url,
                                            "items": []
                                        })
                                        print(f"Found module: {title}")
                            except StaleElementReferenceException:
                                continue
                    except Exception as e:
                        print(f"Selector '{selector}' failed: {e}")
            except Exception as e:
                print(f"Error finding modules via Selenium: {e}")
        
        # If still no modules, try finding any clickable links that look like lessons
        if not modules:
            print("Still no modules found, trying to find lesson links...")
            try:
                # Look for links that might be lessons
                all_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='lesson'], a[href*='module'], a[href*='content'], a[href*='learn']")
                print(f"Found {len(all_links)} potential lesson links")
                
                for link in all_links:
                    try:
                        title = link.text.strip()
                        href = link.get_attribute('href')
                        
                        if title and len(title) > 2 and href:
                            existing = [m for m in modules if m['name'] == title]
                            if not existing:
                                module_id += 1
                                modules.append({
                                    "id": str(module_id),
                                    "name": title,
                                    "lesson_url": href,
                                    "items": []
                                })
                                print(f"Found lesson link: {title}")
                    except:
                        continue
            except Exception as e:
                print(f"Error finding lesson links: {e}")
        
        # Last resort: search for text patterns in page source that look like module names
        if not modules:
            print("Trying text pattern search in page source...")
            import re
            
            # Look for common patterns like "Linear Algebra", "Lesson X", "Module X", etc.
            patterns = [
                r'Linear Algebra[^"<>]*Lesson\s*\d+',
                r'Introduction to[^"<>]{3,50}',
                r'Prerequisites[^"<>]{3,50}',
                r'Lesson\s*\d+[^"<>]{0,50}',
                r'Module\s*\d+[^"<>]{0,50}',
            ]
            
            found_titles = set()
            for pattern in patterns:
                matches = re.findall(pattern, page_source, re.IGNORECASE)
                for match in matches:
                    clean_title = match.strip()
                    if len(clean_title) > 5 and len(clean_title) < 100:
                        found_titles.add(clean_title)
            
            print(f"Found {len(found_titles)} potential module titles via regex")
            for title in sorted(found_titles):
                print(f"  - {title}")
                module_id += 1
                modules.append({
                    "id": str(module_id),
                    "name": title,
                    "lesson_url": "",
                    "items": []
                })
        
        # Also try to find all links on the page and log them for debugging
        if not modules:
            print("\nAll links on page:")
            try:
                all_links = driver.find_elements(By.TAG_NAME, "a")
                for link in all_links[:50]:  # Limit to first 50
                    try:
                        text = link.text.strip()
                        href = link.get_attribute('href') or ""
                        if text and len(text) > 2:
                            print(f"  Link: '{text}' -> {href[:80]}...")
                    except:
                        pass
            except Exception as e:
                print(f"Error listing links: {e}")
        
        # Try to expand all sections by clicking on dropdown options
        # This helps get all 16 modules if they're split across sections
        try:
            # Look for select elements or dropdown triggers
            selects = driver.find_elements(By.CSS_SELECTOR, "select")
            for select in selects:
                options = select.find_elements(By.TAG_NAME, "option")
                for option in options:
                    try:
                        option_text = option.text.strip()
                        if option_text and option_text not in ['Select', 'All', '']:
                            # Click the option to load that section
                            option.click()
                            time.sleep(2)
                            
                            # Parse the new table content
                            new_soup = BeautifulSoup(driver.page_source, 'html.parser')
                            new_table = new_soup.find('table')
                            
                            if new_table:
                                new_rows = new_table.find_all('tr')
                                for row in new_rows:
                                    if row.find('th'):
                                        continue
                                    
                                    cells = row.find_all('td')
                                    if len(cells) >= 2:
                                        title = cells[1].get_text(strip=True) if len(cells) > 1 else cells[0].get_text(strip=True)
                                        
                                        # Check if this module is already in our list
                                        if title and len(title) > 2:
                                            existing = [m for m in modules if m['name'] == title]
                                            if not existing:
                                                module_id += 1
                                                link = row.find('a')
                                                lesson_url = ""
                                                if link and link.get('href'):
                                                    href = link.get('href')
                                                    lesson_url = href if href.startswith('http') else urljoin(course_url, href)
                                                
                                                modules.append({
                                                    "id": str(module_id),
                                                    "name": title,
                                                    "lesson_url": lesson_url,
                                                    "section": option_text,
                                                    "items": []
                                                })
                    except Exception as e:
                        print(f"Error clicking option: {e}")
        except Exception as e:
            print(f"Error expanding sections: {e}")
        
        print(f"Found {len(modules)} modules, now scanning each for videos...")
        
        # Store the modules page URL to return to after scanning each module
        modules_page_url = driver.current_url
        print(f"Modules page URL: {modules_page_url}")
        
        # Now navigate to each module to detect videos
        for idx, module in enumerate(modules):
            try:
                print(f"\nScanning module {idx+1}/{len(modules)}: {module['name']}")
                
                navigated = False
                
                # Method 1: Use lesson_url if available
                if module.get("lesson_url"):
                    print(f"  Navigating via URL: {module['lesson_url']}")
                    driver.get(module["lesson_url"])
                    navigated = True
                    time.sleep(3)
                else:
                    # Method 2: Click on the row element directly
                    # First, go back to modules page to find the row
                    print(f"  No URL, going back to modules page to click row...")
                    driver.get(modules_page_url)
                    time.sleep(2)
                    
                    # Find and click the row with this module's title
                    try:
                        # Try to find the row by its title text
                        row_xpath = f"//tr[contains(., '{module['name'][:30]}')]"
                        row = driver.find_element(By.XPATH, row_xpath)
                        
                        # Try clicking on a link inside the row first
                        try:
                            link = row.find_element(By.TAG_NAME, "a")
                            link.click()
                            navigated = True
                            print(f"  Clicked link in row")
                        except:
                            # Click on the row itself
                            row.click()
                            navigated = True
                            print(f"  Clicked row directly")
                        
                        time.sleep(3)
                    except Exception as click_e:
                        print(f"  Could not click row: {click_e}")
                        
                        # Method 3: Try finding by partial text match
                        try:
                            clickable = driver.find_element(By.XPATH, f"//*[contains(text(), '{module['name'][:20]}')]")
                            clickable.click()
                            navigated = True
                            print(f"  Clicked element with matching text")
                            time.sleep(3)
                        except Exception as text_e:
                            print(f"  Could not find clickable element: {text_e}")
                
                if not navigated:
                    print(f"  Skipping - could not navigate to module")
                    continue
                
                # Check if we're on a different page (module detail page)
                current_url = driver.current_url
                print(f"  Current URL: {current_url}")
                
                # Use the video detection function (like browser extensions)
                detected_videos = detect_video_urls_from_page(driver, course_url)
                print(f"  Detected {len(detected_videos)} videos")
                
                for vid_idx, video in enumerate(detected_videos):
                    video_url = video.get('url', '')
                    if video_url:
                        # Determine video name
                        video_name = f"{module['name']} - Video"
                        if len(detected_videos) > 1:
                            video_name = f"{module['name']} - Video {vid_idx + 1}"
                        
                        module["items"].append({
                            "type": "video",
                            "name": video_name,
                            "url": video_url
                        })
                
                # Also look for PDFs and other resources
                video_soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                # Find PDF links
                pdf_links = video_soup.select("a[href*='.pdf'], a[href*='pdf']")
                for pdf in pdf_links:
                    pdf_url = pdf.get('href')
                    if pdf_url:
                        full_url = pdf_url if pdf_url.startswith('http') else urljoin(course_url, pdf_url)
                        module["items"].append({
                            "type": "pdf",
                            "name": pdf.get_text(strip=True) or f"{module['name']} - PDF",
                            "url": full_url
                        })
                
                # Check for downloadable resources
                download_links = video_soup.select("a[download], a[href*='download']")
                for link in download_links:
                    link_url = link.get('href')
                    if link_url:
                        full_url = link_url if link_url.startswith('http') else urljoin(course_url, link_url)
                        module["items"].append({
                            "type": "file",
                            "name": link.get_text(strip=True) or "Resource",
                            "url": full_url
                        })
                
                print(f"  Found {len(module['items'])} items in {module['name']}")
                        
            except Exception as e:
                print(f"Error scraping module {module['name']}: {e}")
                import traceback
                traceback.print_exc()
        
        # Clean up row_element references (can't be serialized to JSON)
        for module in modules:
            if 'row_element' in module:
                del module['row_element']
        
        # Final summary
        print(f"\n=== SCRAPING SUMMARY ===")
        print(f"Total modules found: {len(modules)}")
        for i, m in enumerate(modules, 1):
            print(f"  {i}. {m['name']} - {len(m.get('items', []))} items")
        print(f"========================\n")
        
        return modules
        
    except Exception as e:
        print(f"Error scraping QpiAI modules: {e}")
        import traceback
        traceback.print_exc()
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
    
    # Use custom download path if provided, otherwise use default
    if request.download_path and request.download_path.strip():
        # Use the custom path provided by user
        download_dir = os.path.join(request.download_path.strip(), f"course_download_{download_id[:8]}")
    else:
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
        course_url = session.get("course_url", "")
        
        # Filter selected modules - if module_ids is empty, download ALL modules
        if module_ids and len(module_ids) > 0:
            selected_modules = [m for m in modules if m["id"] in module_ids]
        else:
            selected_modules = modules  # Download everything
        
        # Count total items
        total_items = sum(len(m.get("items", [])) for m in selected_modules)
        download_progress[download_id]["total_items"] = total_items
        download_progress[download_id]["status"] = "downloading"
        
        # Create requests session with cookies and proper headers (like browser extensions)
        req_session = requests.Session()
        for cookie in cookies:
            req_session.cookies.set(cookie['name'], cookie['value'])
        
        # Set headers to mimic browser (important for CDN/video downloads)
        req_session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
        
        completed = 0
        
        for module in selected_modules:
            module_name = sanitize_filename(module["name"])
            module_dir = os.path.join(download_dir, module_name)
            os.makedirs(module_dir, exist_ok=True)
            
            # Get the lesson URL for Referer header
            lesson_url = module.get("lesson_url", course_url)
            
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
                        
                        # Set Referer header (important for video CDNs)
                        headers = {'Referer': lesson_url or course_url}
                        
                        # Download file with proper headers
                        response = req_session.get(item_url, stream=True, timeout=300, headers=headers)
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


# ============= NEW API-BASED VIDEO EXTRACTION =============
# This approach uses the QpiAI API with JWT token to get course structure
# and then visits each lesson page to extract video URLs

class APILoginRequest(BaseModel):
    course_url: str
    username: str
    password: str

class VideoDownloadRequest(BaseModel):
    session_id: str
    video_urls: list[dict]  # List of {url, filename, module, chapter}
    download_path: str = ""

@app.post("/api/extract-videos")
async def extract_videos_api(request: LoginRequest, background_tasks: BackgroundTasks):
    """
    Login to QpiAI, get JWT token, fetch course structure via API,
    then visit each lesson page to extract video URLs.
    
    This is more reliable than DOM scraping because:
    1. Uses the official API to get course structure
    2. Only needs to visit lesson pages to get video URLs
    3. Videos are direct S3 MP4 files (no DRM)
    """
    session_id = str(uuid.uuid4())
    
    try:
        driver = get_chrome_driver()
        
        # Step 1: Login and get JWT token
        print("Step 1: Logging in to get JWT token...")
        if not login_qpiai_explorer(driver, request.course_url, request.username, request.password):
            driver.quit()
            raise HTTPException(status_code=401, detail="Login failed")
        
        # Get JWT token from cookies
        cookies = driver.get_cookies()
        jwt_token = None
        for cookie in cookies:
            if cookie['name'] == 'explorer-token':
                jwt_token = cookie['value']
                break
        
        if not jwt_token:
            driver.quit()
            raise HTTPException(status_code=401, detail="Could not get authentication token")
        
        print(f"Got JWT token: {jwt_token[:50]}...")
        
        # Step 2: Use API to get course structure
        print("Step 2: Fetching course structure from API...")
        
        # Extract course slug from URL
        course_slug = "quantum-expert-with-amazon-braket"
        if "/learn/" in request.course_url:
            parts = request.course_url.split("/learn/")
            if len(parts) > 1:
                course_slug = parts[1].split("/")[0]
        
        api_base = "https://server-explorer-dev.qpiai.tech/api"
        headers = {"Authorization": f"Bearer {jwt_token}"}
        
        # Get modules
        modules_response = requests.get(
            f"{api_base}/courses/{course_slug}/modules",
            headers=headers
        )
        
        if modules_response.status_code != 200:
            driver.quit()
            raise HTTPException(status_code=500, detail="Failed to fetch course modules from API")
        
        modules_data = modules_response.json()
        print(f"Found {len(modules_data)} modules from API")
        
        # Build lesson URLs from API data
        all_lessons = []
        for module in modules_data:
            module_id = module['_id']
            module_name = module['title']
            
            for chapter in module.get('chapters', []):
                chapter_id = chapter['_id']
                chapter_name = chapter['title']
                
                for lesson_id in chapter.get('lessons', []):
                    lesson_url = f"https://explorer-dev.qpiai.tech/learn/{course_slug}/modules/{module_id}/chapters/{chapter_id}/lessons/{lesson_id}"
                    all_lessons.append({
                        'lesson_id': lesson_id,
                        'lesson_url': lesson_url,
                        'module_name': module_name,
                        'chapter_name': chapter_name
                    })
        
        print(f"Total lessons to scan: {len(all_lessons)}")
        
        # Step 3: Visit each lesson page and extract video URL
        print("Step 3: Extracting video URLs from lesson pages...")
        
        videos = []
        for i, lesson in enumerate(all_lessons):
            try:
                print(f"Scanning lesson {i+1}/{len(all_lessons)}: {lesson['lesson_url'][:80]}...")
                driver.get(lesson['lesson_url'])
                time.sleep(3)  # Wait for video to load
                
                # Get lesson title
                try:
                    title_elem = driver.find_element(By.CSS_SELECTOR, "h1")
                    lesson_title = title_elem.text.strip()
                except:
                    lesson_title = f"Lesson_{i+1}"
                
                # Get video URL
                video_url = driver.execute_script("""
                    var video = document.querySelector('video');
                    return video ? (video.src || video.currentSrc) : null;
                """)
                
                if video_url and video_url.startswith('http'):
                    videos.append({
                        'title': lesson_title,
                        'url': video_url,
                        'module': lesson['module_name'],
                        'chapter': lesson['chapter_name'],
                        'lesson_id': lesson['lesson_id']
                    })
                    print(f"  Found video: {lesson_title[:50]}...")
                else:
                    print(f"  No video found for lesson {i+1}")
                    
            except Exception as e:
                print(f"  Error scanning lesson {i+1}: {e}")
                continue
        
        driver.quit()
        
        # Store in session
        sessions[session_id] = {
            "course_url": request.course_url,
            "jwt_token": jwt_token,
            "videos": videos,
            "total_lessons": len(all_lessons),
            "modules": modules_data
        }
        
        # Save videos to files for later use
        output_dir = DOWNLOAD_BASE_DIR
        os.makedirs(output_dir, exist_ok=True)
        
        # Save as JSON
        json_file = os.path.join(output_dir, "video_urls.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump({
                "course_url": request.course_url,
                "total_videos": len(videos),
                "total_lessons": len(all_lessons),
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
            "success": True,
            "session_id": session_id,
            "total_videos": len(videos),
            "total_lessons": len(all_lessons),
            "videos": videos,
            "files_saved": {
                "json": json_file,
                "csv": csv_file,
                "txt": txt_file
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in extract_videos_api: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/download-videos")
async def download_videos(request: VideoDownloadRequest, background_tasks: BackgroundTasks):
    """Download videos from the extracted URLs"""
    
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[request.session_id]
    download_id = str(uuid.uuid4())
    
    # Determine download path
    download_path = request.download_path if request.download_path else DOWNLOAD_BASE_DIR
    
    # Initialize progress
    download_progress[download_id] = {
        "status": "starting",
        "total_items": len(request.video_urls),
        "completed_items": 0,
        "current_item": "",
        "errors": []
    }
    
    # Start download in background
    background_tasks.add_task(
        download_videos_task,
        download_id,
        request.video_urls,
        download_path
    )
    
    return {
        "success": True,
        "download_id": download_id,
        "message": f"Started downloading {len(request.video_urls)} videos"
    }


async def download_videos_task(download_id: str, videos: list, download_path: str):
    """Background task to download videos"""
    
    try:
        download_progress[download_id]["status"] = "downloading"
        
        for i, video in enumerate(videos):
            try:
                url = video.get('url')
                title = video.get('title', f'video_{i+1}')
                module = video.get('module', 'Unknown')
                chapter = video.get('chapter', '')
                
                # Create folder structure: download_path/module/chapter/
                safe_module = sanitize_filename(module)
                safe_chapter = sanitize_filename(chapter) if chapter else ""
                
                if safe_chapter:
                    folder_path = os.path.join(download_path, safe_module, safe_chapter)
                else:
                    folder_path = os.path.join(download_path, safe_module)
                
                os.makedirs(folder_path, exist_ok=True)
                
                # Create filename
                safe_title = sanitize_filename(title)
                filename = f"{safe_title}.mp4"
                filepath = os.path.join(folder_path, filename)
                
                # Skip if already exists
                if os.path.exists(filepath):
                    print(f"Skipping (exists): {filename}")
                    download_progress[download_id]["completed_items"] = i + 1
                    continue
                
                download_progress[download_id]["current_item"] = title
                
                # Download the video
                print(f"Downloading: {title}")
                response = requests.get(url, stream=True, headers={
                    "User-Agent": USER_AGENT
                })
                
                if response.status_code == 200:
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    print(f"Downloaded: {filename}")
                else:
                    download_progress[download_id]["errors"].append(f"Failed to download {title}: HTTP {response.status_code}")
                
                download_progress[download_id]["completed_items"] = i + 1
                
            except Exception as e:
                download_progress[download_id]["errors"].append(f"Error downloading {video.get('title', 'unknown')}: {str(e)}")
                download_progress[download_id]["completed_items"] = i + 1
        
        download_progress[download_id]["status"] = "completed"
        download_progress[download_id]["current_item"] = ""
        
    except Exception as e:
        download_progress[download_id]["status"] = "error"
        download_progress[download_id]["errors"].append(str(e))
