import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def launch_whatsapp(PROFILES_DIR):
    """Launch WhatsApp Web with a specific Chrome user profile."""
    try:
        options = Options()
        options.add_argument(f"--user-data-dir={PROFILES_DIR}")
        options.add_argument("--profile-directory=Default")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        logger.info(f"Launching Chrome with profile at {PROFILES_DIR}")

        browser = webdriver.Chrome(options=options)
        wait = WebDriverWait(browser, timeout=30)

        logger.info("Chrome browser launched successfully")
        return browser, wait

    except Exception as e:
        logger.error(f"Failed to launch WhatsApp Web with Chrome: {e}")
        raise
