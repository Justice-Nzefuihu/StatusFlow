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

def phone_number_login():
    select_clickable_element("//div[contains(text(), 'Log in with phone number')]")
    select_clickable_element("//button[.//span[contains(@data-icon, 'chevron')]]")
    country = 'Nigeria'
    type_text("//p[contains(@class, 'selectable-text copyable-text')]", country)
    select_clickable_element( "(//button[contains(@aria-label, 'Selected country:')])[1]")
    phone_number = '9043262304'
    type_text("//input[contains(@aria-label, 'phone number')]", phone_number)
    select_clickable_element("(//button[.//div[contains(text(),'Next')]])[1]")
    link_code = get_code()
    print("Link Code:", link_code)
    input("After linking device, press Enter...")

def login_or_restore():
    browser.get("https://web.whatsapp.com/")
    try:
        select_clickable_element("//button[.//div[contains(text(), 'Continue')]]")
    except TimeoutException:
        pass
    try:
        select_clickable_element("(//button[contains(@aria-label,'Status')])[1]")
    except TimeoutException:
        phone_number_login()

def get_code():
    link_code_element = select_element("(//div[contains(@aria-details, 'device-phone-number-code-screen')])[1]")
    wait.until(lambda d: link_code_element.get_attribute('data-link-code') is not None)
    link_code = link_code_element.get_attribute('data-link-code').replace(',', '').strip()
    return link_code

def send_status_images():
    select_clickable_element("(//button[contains(@aria-label,'Status')])[2]")
    input()
    select_clickable_element("//div[contains(@role, 'application')]//ul//li[.//span[contains(text(), 'video')]]")
    # text_element = update_status_ul_element[1]
    # click(image_element)

    statuses = [
        (r"C:\Users\HP\Desktop\Hotel\Juel\media\photos\2023\11\27\about4.jpg",'room 1'),(r"C:\Users\HP\Desktop\Hotel\Juel\media\photos\2023\11\27\about4.jpg", 'room 2')
        ]
    for i, (file_path, caption) in enumerate(statuses):
        pyautogui.write(file_path)
        pyautogui.press("enter")
        sleep(2)
        type_text("//div[@aria-label='Add a caption']//p[contains(@class,'selectable-text copyable-text')]", caption)
        if i < len(statuses)-1:
            select_clickable_element("//button[contains(@title, 'Add file')]")
    
    select_clickable_element("//div[contains(@aria-label, 'Send')]")

def main():
    print("in the main function")
    login_or_restore()
    try:
        ok_element = select_clickable_element("//button[.//div[contains(text(), 'OK')]]")
        if ok_element:
            print("inside the ok element")
            main()
    except TimeoutException:
        pass
    send_status_images()
    browser.quit()

if __name__ == "__main__":
    print("hello world")
    browser = launch_whatsapp_session('justice_nzefuihu')
    wait = WebDriverWait(browser, timeout=10)
    print("In the if statement")
    main()