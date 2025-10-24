import logging
import pyautogui
from time import sleep
from .whatsapp_utils import select_clickable_element, type_text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def send_status_texts(write_ups, phone, country, browser, wait):
    try:
        logger.info(f"Starting to send text statuses for {phone} ({country})")

        select_clickable_element(wait, browser, "(//button[contains(@aria-label,'Status')])")
        select_clickable_element(wait, browser, "//div[contains(@aria-label,'Add Status')]//div")
        select_clickable_element(wait, browser, "//div[contains(@role, 'application')]//ul//li[.//span[contains(text(), 'Text')]]//div")

        for i, write_up in enumerate(write_ups):
            logger.info(f"Typing status {i+1}/{len(write_ups)}: {write_up[:30]}...")

            type_text(wait, "//div[@aria-placeholder='Type a status']//p[contains(@class,'selectable-text copyable-text')]", write_up)
            select_clickable_element(wait, browser, "//div[contains(@aria-label, 'Send')]")

            if i < len(write_ups) - 1:
                select_clickable_element(wait, browser, "(//button[contains(@aria-label,'Status')])")
                select_clickable_element(wait, browser, "//div[contains(@aria-label,'Add Status')]//div")
                select_clickable_element(wait, browser, "//div[contains(@role, 'application')]//ul//li[.//span[contains(text(), 'Text')]]//div")

                sleep(5)

        logger.info("All text statuses sent successfully.")
        sleep(60)

    except Exception as e:
        logger.error(f"Error while sending text statuses for {phone} ({country}): {e}", exc_info=True)
        raise


def send_status_images(images, phone, country, browser, wait):
    try:
        logger.info(f"Starting to send image statuses for {phone} ({country})")

        select_clickable_element(wait, browser, "(//button[contains(@aria-label,'Status')])")
        select_clickable_element(wait, browser, "//div[contains(@aria-label,'Add Status')]//div")
        select_clickable_element(wait, browser, "//div[contains(@role, 'application')]//ul//li[.//span[contains(text(), 'video')]]//div")

        for i, (image_path, caption) in enumerate(images):
            logger.info(f"Uploading image {i+1}/{len(images)}: {image_path}")

            pyautogui.write(image_path)
            pyautogui.press("enter")
            sleep(5)

            logger.info(f"Adding caption: {caption[:30]}...")
            type_text(wait, "//div[@aria-label='Add a caption']//p[contains(@class,'selectable-text copyable-text')]", caption)

            if i < len(images) - 1:
                select_clickable_element(wait, browser, "//button[contains(@title, 'Add file')]")

        select_clickable_element(wait, browser, "//div[contains(@aria-label, 'Send')]")
        logger.info("All image statuses sent successfully.")
        sleep(60)

    except Exception as e:
        logger.error(f"Error while sending image statuses for {phone} ({country}): {e}", exc_info=True)
        raise
        
