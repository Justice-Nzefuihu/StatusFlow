from time import sleep
from whatsapp_utils import select_clickable_element, type_text, select_element
from selenium.common.exceptions import TimeoutException
from main import launch_whatsapp

def phone_number_login(wait, browser, phone_number, country):
    select_clickable_element(wait, browser, "//div[contains(text(), 'Log in with phone number')]")
    select_clickable_element(wait, browser, "//button[.//span[contains(@data-icon, 'chevron')]]")

    type_text(wait, "//p[contains(@class, 'selectable-text copyable-text')]", country)
    select_clickable_element(wait, browser, "(//button[contains(@aria-label, 'Selected country:')])[1]")

    type_text(wait, "//input[contains(@aria-label, 'phone number')]", phone_number)
    select_clickable_element(wait, browser, "(//button[.//div[contains(text(),'Next')]])[1]")
    link_code = get_code(wait, browser)
    print("Link Code:", link_code)
    input("After linking device, press Enter...")
    sleep(30)

def login_or_restore(user_id, phone_number, country):
    browser, wait = launch_whatsapp(str(user_id))
    browser.get("https://web.whatsapp.com/")
    try:
        select_clickable_element(wait, browser, "//button[.//div[contains(text(), 'Continue')]]")
    except TimeoutException:
        pass
    try:
        select_clickable_element(wait, browser, "(//button[contains(@aria-label,'Status')])[1]")
    except TimeoutException:
        phone_number_login(wait, browser, phone_number, country)
        try:
            ok_element = select_clickable_element("//button[.//div[contains(text(), 'OK')]]")
            if ok_element:
                login_or_restore(user_id, phone_number, country)
        except TimeoutException:
            pass

    sleep(60)
    browser.quit()

def get_code(wait, browser):
    link_code_element = select_element(wait, browser, "(//div[contains(@aria-details, 'device-phone-number-code-screen')])[1]")
    wait.until(lambda d: link_code_element.get_attribute('data-link-code') is not None)
    link_code = link_code_element.get_attribute('data-link-code').replace(',', '').strip()
    return link_code