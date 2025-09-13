from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

def launch_whatsapp(PROFILES_DIR):

    options = Options()
    options.add_argument(f"--user-data-dir={PROFILES_DIR}")
    options.add_argument("--profile-directory=Default")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    browser = webdriver.Chrome(options=options)
    wait = WebDriverWait(browser, timeout=10)
    return browser, wait
    
