import logging
from time import sleep
from selenium.common.exceptions import TimeoutException, WebDriverException
from .whatsapp_utils import select_clickable_element, type_text, select_element
from .main import launch_whatsapp
from .login_status import get_login_status, change_login_status

logger = logging.getLogger(__name__)

def phone_number_login(wait, browser, phone_number: str, country: str):
    try:
        logger.info("Attempting login with phone number %s (%s)", phone_number, country)

        select_clickable_element(wait, browser, "//div[contains(text(), 'Log in with phone number')]")
        select_clickable_element(wait, browser, "//button[.//span[contains(@data-icon, 'chevron')]]")

        type_text(wait, "//p[contains(@class, 'selectable-text copyable-text')]", country)
        select_clickable_element(wait, browser, "(//button[contains(@aria-label, 'Selected country:')])[1]")

        type_text(wait, "//input[contains(@aria-label, 'phone number')]", phone_number)

        get_code(wait, browser, phone_number, country)

        logger.info("Login flow initiated for %s (%s)", phone_number, country)

    except Exception as e:
        logger.error("Error during phone number login for %s (%s): %s", phone_number, country, e, exc_info=True)
        raise


def login_or_restore(phone_number: str, country: str, PROFILES_DIR):
    logger.info("Launching WhatsApp Web for %s (%s)", phone_number, country)
    try:
        browser, wait = launch_whatsapp(str(PROFILES_DIR))
        browser.get("https://web.whatsapp.com/")
    except WebDriverException as e:
        logger.error("Failed to launch WhatsApp Web for %s (%s): %s", phone_number, country, e, exc_info=True)
        raise

    try:
        select_clickable_element(wait, browser, "//button[.//div[contains(text(), 'Continue')]]")
        logger.info("Continue button clicked for %s (%s)", phone_number, country)
    except TimeoutException:
        logger.debug("No 'Continue' button detected for %s (%s)", phone_number, country)

    try:
        select_clickable_element(wait, browser, "(//button[contains(@aria-label,'Status')])[1]")
        logger.info("Existing session restored for %s (%s)", phone_number, country)
    except TimeoutException:
        logger.warning("Session not found, attempting phone number login for %s (%s)", phone_number, country)
        try:
            changed = change_login_status(phone_number, country)
            if changed:
                phone_number_login(wait, browser, phone_number, country)
            else:
                raise Exception("Unable to change login status or detect new user")
        except Exception as e:
            logger.error("Failed during login_or_restore for %s (%s): %s", phone_number, country, e, exc_info=True)
            browser.quit()
            raise

    logger.info("Waiting to complete login for %s (%s)...", phone_number, country)
    sleep(120)
    browser.quit()
    logger.info("Closed browser for %s (%s)", phone_number, country)

    return browser, wait


def get_code(wait, browser, phone_number: str, country: str):
    logger.info("Requesting link code for %s (%s)", phone_number, country)
    try:
        select_clickable_element(wait, browser, "(//button[.//div[contains(text(),'Next')]])[1]")

        link_code_element = select_element(wait, "(//div[contains(@aria-details, 'device-phone-number-code-screen')])[1]")
        wait.until(lambda d: link_code_element.get_attribute('data-link-code') is not None)
        link_code = link_code_element.get_attribute('data-link-code').replace(',', '').strip()
        logger.info("Link code retrieved for %s (%s): %s", phone_number, country, link_code)

        for num in range(60):  # wait up to 60 × 5s = 5 minutes
            if get_login_status(phone_number, country):
                logger.info("Login confirmed for %s (%s)", phone_number, country)
                break
            try:
                select_clickable_element(wait, browser, "//div[contains(@aria-label,'Something went wrong Please try again or link with the QR code.')]//button")
                logger.warning("Retrying get_code due to error prompt for %s (%s)", phone_number, country)
                return get_code(wait, browser, phone_number, country)
            except TimeoutException:
                pass
            logger.debug("Waiting for login confirmation (%s/%s) for %s (%s)", num + 1, 60, phone_number, country)
            sleep(5)
        else:
            raise Exception("Login not confirmed within timeout for %s (%s)" % (phone_number, country))

        sleep(60)

    except Exception as e:
        logger.error("Error in get_code for %s (%s): %s", phone_number, country, e, exc_info=True)
        raise
