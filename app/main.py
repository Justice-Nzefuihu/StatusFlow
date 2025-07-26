import os
import pathlib
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
PROFILES_DIR = os.path.join(BASE_DIR, "profiles")
os.makedirs(PROFILES_DIR, exist_ok=True)

def launch_whatsapp(user_id):
    user_profile_path = os.path.join(PROFILES_DIR, user_id)
    os.makedirs(user_profile_path, exist_ok=True)

    options = Options()
    options.add_argument(f"--user-data-dir={user_profile_path}")
    options.add_argument("--profile-directory=Default")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    browser = webdriver.Chrome(options=options)
    wait = WebDriverWait(browser, timeout=10)
    return browser, wait
    
