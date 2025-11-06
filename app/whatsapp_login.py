import pathlib
from time import sleep
from selenium.common.exceptions import TimeoutException, WebDriverException
from .whatsapp_utils import select_clickable_element, type_text, select_element
from .main import launch_whatsapp
from .login_status import get_login_status, change_login_status


from app.logging_config import get_logger

logger = get_logger(__name__)

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


def login_or_restore(phone_number: str, country: str, PROFILES_DIR, for_status: bool = False):
    logger.info("Launching WhatsApp Web for %s (%s)", phone_number, country)
    try:
        browser, wait = launch_whatsapp(str(PROFILES_DIR))
        browser.get("https://web.whatsapp.com/")
        re_uploading = False
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
                if for_status:
                    MAIN_DIR = pathlib.Path(PROFILES_DIR).resolve().parent

                    if MAIN_DIR.exists():
                        re_uploading = True
                        logger.info(f"Queued profile upload for {MAIN_DIR}")
                    else:
                        logger.error(f"Upload directory not found: {MAIN_DIR}")

            else:
                raise Exception("Unable to change login status or detect new user")
        except Exception as e:
            logger.error("Failed during login_or_restore for %s (%s): %s", phone_number, country, e, exc_info=True)
            browser.quit()
            raise
    
    logger.info("Waiting to complete login for %s (%s)...", phone_number, country)
    sleep(60)
    
    if not for_status:
        browser.quit()
        logger.info("Closed browser for %s (%s)", phone_number, country)

    return browser, wait, re_uploading


def get_code(wait, browser, phone_number: str, country: str):
    logger.info("Requesting link code for %s (%s)", phone_number, country)
    try:
        select_clickable_element(wait, browser, "(//button[.//div[contains(text(),'Next')]])[1]")

        for num in range(60):  # wait up to 5 minutes (60 × 5s)
            try:
                link_code_element = select_element(wait, "(//div[contains(@aria-details, 'device-phone-number-code-screen')])[1]")
                wait.until(lambda d: link_code_element.get_attribute('data-link-code') is not None)
                link_code = link_code_element.get_attribute('data-link-code').replace(',', '').strip()
                logger.info("Link code retrieved for %s (%s): %s", phone_number, country, link_code)
            except TimeoutException:
                logger.debug("Link code not yet available for %s (%s)", phone_number, country)

            # Check if login is confirmed and send verification mssg
            if get_login_status(phone_number, country, link_code):
                logger.info("Login confirmed for %s (%s)", phone_number, country)
                break

            # Retry if WhatsApp shows “Something went wrong”
            try:
                select_clickable_element(
                    wait, browser,
                    "//div[contains(@aria-label,'Something went wrong Please try again or link with the QR code.')]//button"
                )
                logger.warning("Retrying get_code due to error prompt for %s (%s)", phone_number, country)
                return get_code(wait, browser, phone_number, country)
            except TimeoutException:
                pass  # Ignore if the error popup isn’t found

            logger.debug(
                "Waiting for login confirmation (%s/%s) for %s (%s)",
                num + 1, 60, phone_number, country
            )
            sleep(5)

        else:
            # Timeout after all 60 attempts
            logger.warning("Login not confirmed within timeout for %s (%s)", phone_number, country)
            raise TimeoutException(f"Login not confirmed for {phone_number} ({country}) within timeout")

        sleep(30)  # Give WhatsApp time to finalize session

    except TimeoutException as e:
        logger.warning("Timeout while getting code for %s (%s): %s", phone_number, country, str(e))
        raise

    except WebDriverException as e:
        logger.warning("WebDriver issue during get_code for %s (%s): %s", phone_number, country, str(e))
        raise

    except Exception as e:
        # Only unexpected errors get full tracebacks
        logger.error("Unexpected error in get_code for %s (%s): %s", phone_number, country, str(e), exc_info=True)
        raise
