from main import launch_whatsapp
import pyautogui
from whatsapp_utils import select_clickable_element, type_text
from time import sleep

def send_status_texts(write_ups, PROFILE_DIR):
    browser, wait = launch_whatsapp(str( PROFILE_DIR))
    select_clickable_element(wait, browser, "(//button[contains(@aria-label,'Status')])[2]")
    select_clickable_element(wait, browser, "//div[contains(@role, 'application')]//ul//li[.//span[contains(text(), 'Text')]]")

    for i, write_up in enumerate(write_ups):
        type_text(wait, "//div[@aria-placeholder='Type a status']//p[contains(@class,'selectable-text copyable-text')]", write_up)
        select_clickable_element(wait, browser, "//div[contains(@aria-label, 'Send')]")

        if i < len(write_ups)-1:
            select_clickable_element(wait, browser, "(//button[contains(@aria-label,'Status')])[2]")
            select_clickable_element(wait, browser, "//div[contains(@role, 'application')]//ul//li[.//span[contains(text(), 'Text')]]")
    
    sleep(120)
    browser.quit()
        
def send_status_images(images,  PROFILE_DIR):
    browser, wait = launch_whatsapp(str( PROFILE_DIR))
    select_clickable_element(wait, browser, "(//button[contains(@aria-label,'Status')])[2]")
    select_clickable_element(wait, browser, "//div[contains(@role, 'application')]//ul//li[.//span[contains(text(), 'video')]]")

    for i, (image_path, caption) in enumerate(images):
        pyautogui.write(image_path)
        pyautogui.press("enter")
        sleep(2)

        type_text(wait, "//div[@aria-label='Add a caption']//p[contains(@class,'selectable-text copyable-text')]", caption)

        if i < len(images)-1:
            select_clickable_element(wait, browser, "//button[contains(@title, 'Add file')]")
    
    select_clickable_element(wait, browser, "//div[contains(@aria-label, 'Send')]")

    sleep(120)
    browser.quit()