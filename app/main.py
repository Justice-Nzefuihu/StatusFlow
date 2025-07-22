import pyautogui
import os
import pathlib
from selenium import webdriver
from time import sleep
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
from .database import sessionLocal
from .model import  UserDB

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
PROFILES_DIR = os.path.join(BASE_DIR, "profiles")
os.makedirs(PROFILES_DIR, exist_ok=True)

def launch_whatsapp_session(user_id):
    user_profile_path = os.path.join(PROFILES_DIR, user_id)
    os.makedirs(user_profile_path, exist_ok=True)

    options = Options()
    options.add_argument(f"--user-data-dir={user_profile_path}")
    options.add_argument("--profile-directory=Default")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    browser = webdriver.Chrome(options=options)
    return browser

def select_element(xpath):
    return wait.until(EC.presence_of_element_located((By.XPATH, xpath)))

def select_clickable_element(xpath):
    element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
    browser.execute_script("arguments[0].scrollIntoView(true);", element)
    element.click()
    sleep(5)
    return element

def click(element):
    browser.execute_script("arguments[0].scrollIntoView(true);", element)
    element.click()
    sleep(5)

def type_text(xpath, value):
    element = select_element(xpath)
    element.clear()
    for letter in value:
        element.send_keys(letter)
        sleep(0.1)
    sleep(2)

def phone_number_login(user : UserDB):
    select_clickable_element("//div[contains(text(), 'Log in with phone number')]")
    select_clickable_element("//button[.//span[contains(@data-icon, 'chevron')]]")

    country = user.country
    type_text("//p[contains(@class, 'selectable-text copyable-text')]", country)
    select_clickable_element( "(//button[contains(@aria-label, 'Selected country:')])[1]")

    phone_number = user.phone
    type_text("//input[contains(@aria-label, 'phone number')]", phone_number)
    select_clickable_element("(//button[.//div[contains(text(),'Next')]])[1]")
    link_code = get_code()
    print("Link Code:", link_code)
    input("After linking device, press Enter...")
    sleep(30)

def login_or_restore(user : UserDB):
    browser.get("https://web.whatsapp.com/")

    try:
        select_clickable_element("//button[.//div[contains(text(), 'Continue')]]")
    except TimeoutException:
        pass

    try:
        select_clickable_element("(//button[contains(@aria-label,'Status')])[1]")
    except TimeoutException:
        phone_number_login(user)

def get_code():
    link_code_element = select_element("(//div[contains(@aria-details, 'device-phone-number-code-screen')])[1]")
    wait.until(lambda d: link_code_element.get_attribute('data-link-code') is not None)
    link_code = link_code_element.get_attribute('data-link-code').replace(',', '').strip()
    return link_code

def send_status_text(write_ups):
    if write_ups:
        select_clickable_element("(//button[contains(@aria-label,'Status')])[2]")
        select_clickable_element("//div[contains(@role, 'application')]//ul//li[.//span[contains(text(), 'Text')]]")

        for i, write_up in enumerate(write_ups):
            type_text("//div[@aria-placeholder='Type a status']//p[contains(@class,'selectable-text copyable-text')]", write_up)
            select_clickable_element("//div[contains(@aria-label, 'Send')]")

            if i < len(write_ups)-1:
                select_clickable_element("(//button[contains(@aria-label,'Status')])[2]")
                select_clickable_element("//div[contains(@role, 'application')]//ul//li[.//span[contains(text(), 'Text')]]")
        
def send_status_images(images):
    if images:
        select_clickable_element("(//button[contains(@aria-label,'Status')])[2]")
        select_clickable_element("//div[contains(@role, 'application')]//ul//li[.//span[contains(text(), 'video')]]")

        for i, (image_path, caption) in enumerate(images):
            pyautogui.write(image_path)
            pyautogui.press("enter")
            sleep(2)

            type_text("//div[@aria-label='Add a caption']//p[contains(@class,'selectable-text copyable-text')]", caption)

            if i < len(images)-1:
                select_clickable_element("//button[contains(@title, 'Add file')]")
        
        select_clickable_element("//div[contains(@aria-label, 'Send')]")

def main():
    login_or_restore(user)

    try:
        ok_element = select_clickable_element("//button[.//div[contains(text(), 'OK')]]")
        if ok_element:
            print("inside the ok element")
            main()
    except TimeoutException:
        pass

    write_ups = []
    images = []
    for status in user.statuses:
        if not status.is_upload:
            if status.is_text:
                write_ups.append(status.write_up)
            else:
                images.append((status.images_path, status.write_up))

    send_status_images(images)
    send_status_text(write_ups)
    sleep(15)
    browser.quit()

def get_or_create_user(phone: str, country: str, db: Session):
    try:
        user = db.query(UserDB).filter_by(phone=phone, country=country).options(
            joinedload(UserDB.statuses)
        ).first()

        if not user:
            user = UserDB(phone=phone, country=country)
            db.add(user)
            db.commit()
            db.refresh(user)

        return user

    except SQLAlchemyError as e:
        db.rollback()
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    try:
        db = sessionLocal()
        user: UserDB = get_or_create_user(db, phone="9043262304", country="Nigeria")
    finally:
        db.close()
    browser = launch_whatsapp_session(user.id)
    wait = WebDriverWait(browser, timeout=10)
    main()