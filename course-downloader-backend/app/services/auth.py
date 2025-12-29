"""
Authentication services for course platforms.
"""
import time
from urllib.parse import urljoin

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from app.core.config import SELENIUM_TIMEOUT, SELENIUM_PAGE_LOAD_WAIT


def is_qpiai_explorer(url: str) -> bool:
    """Check if the URL is a QpiAI Explorer platform."""
    return "qpiai.tech" in url or "explorer" in url.lower()


def login_qpiai_explorer(driver, base_url: str, username: str, password: str) -> bool:
    """
    Login to QpiAI Explorer platform.
    
    Args:
        driver: Selenium WebDriver instance
        base_url: Base URL of the platform
        username: User's email
        password: User's password
        
    Returns:
        True if login successful, False otherwise
    """
    try:
        # Navigate to login page
        login_url = urljoin(base_url, "/auth/signin")
        driver.get(login_url)
        time.sleep(SELENIUM_PAGE_LOAD_WAIT)
        
        # Fill email
        email_field = WebDriverWait(driver, SELENIUM_TIMEOUT).until(
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
        
        time.sleep(SELENIUM_PAGE_LOAD_WAIT)
        
        # Check if login was successful (should redirect away from signin page)
        return "/auth/signin" not in driver.current_url
        
    except Exception as e:
        print(f"QpiAI login error: {e}")
        return False


def get_jwt_token(driver) -> str:
    """
    Extract JWT token from browser cookies or localStorage.
    
    Args:
        driver: Selenium WebDriver instance
        
    Returns:
        JWT token string or empty string if not found
    """
    try:
        # Try to get token from localStorage
        token = driver.execute_script("return localStorage.getItem('token')")
        if token:
            return token
        
        # Try to get from cookies
        cookies = driver.get_cookies()
        for cookie in cookies:
            if 'token' in cookie['name'].lower():
                return cookie['value']
        
        return ""
    except Exception as e:
        print(f"Error getting JWT token: {e}")
        return ""
