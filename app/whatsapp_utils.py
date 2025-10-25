from time import sleep
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, WebDriverException

from app.logging_config import get_logger

logger = get_logger(__name__)

def select_element(wait, xpath: str):
    try:
        logger.debug("Waiting for element presence: %s", xpath)
        element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
        logger.info("Element located: %s", xpath)
        return element
    except TimeoutException:
        logger.warning("Timeout: Element not found at %s", xpath)
        raise
    except Exception as e:
        logger.error("Error selecting element %s: %s", xpath, e, exc_info=True)
        raise


def select_clickable_element(wait, browser, xpath: str):
    try:
        logger.debug("Waiting for clickable element: %s", xpath)
        element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        browser.execute_script("arguments[0].scrollIntoView(true);", element)
        element.click()
        logger.info("Clicked element: %s", xpath)
        sleep(5)
        return element
    except TimeoutException:
        logger.warning("Timeout: Clickable element not found at %s", xpath)
        raise
    except WebDriverException as e:
        logger.error("WebDriver error while clicking %s: %s", xpath, e, exc_info=True)
        raise
    except Exception as e:
        logger.error("Unexpected error clicking element %s: %s", xpath, e, exc_info=True)
        raise


def click(browser, element):
    try:
        logger.debug("Clicking element directly: %s", element)
        browser.execute_script("arguments[0].scrollIntoView(true);", element)
        element.click()
        logger.info("Clicked element successfully")
        sleep(5)
    except WebDriverException as e:
        logger.error("WebDriver error while clicking element: %s", e, exc_info=True)
        raise
    except Exception as e:
        logger.error("Unexpected error while clicking element: %s", e, exc_info=True)
        raise


def type_text(wait, xpath: str, value: str):
    try:
        logger.debug("Typing text into element %s: '%s'", xpath, value)
        element = select_element(wait, xpath)
        element.clear()
        element.send_keys(Keys.CONTROL + "a")
        element.send_keys(Keys.DELETE)

        for letter in value:
            element.send_keys(letter)
            sleep(0.1)

        sleep(2)
        logger.info("Finished typing into element: %s", xpath)
    except TimeoutException:
        logger.warning("Timeout: Element not available for typing at %s", xpath)
        raise
    except WebDriverException as e:
        logger.error("WebDriver error typing into %s: %s", xpath, e, exc_info=True)
        raise
    except Exception as e:
        logger.error("Unexpected error typing into element %s: %s", xpath, e, exc_info=True)
        raise
