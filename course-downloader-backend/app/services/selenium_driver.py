"""
Selenium WebDriver setup and utilities.
"""
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from app.core.config import USER_AGENT


def get_chrome_driver(enable_network_logging: bool = False) -> webdriver.Chrome:
    """
    Create and configure a Chrome WebDriver instance.
    
    Args:
        enable_network_logging: Enable network logging for video URL detection
        
    Returns:
        Configured Chrome WebDriver instance
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(f"--user-agent={USER_AGENT}")
    
    # Enable network logging for video URL detection (like browser extensions)
    if enable_network_logging:
        chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver
