import pyautogui
from selenium import webdriver
from time import sleep
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By


options = Options()
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)

browser = webdriver.Chrome(options=options)
browser.get("https://web.whatsapp.com/")
wait = WebDriverWait(browser, timeout=10)
sleep(5)

def select_element(xpath):
    return wait.until(
    EC.presence_of_element_located(
        (By.XPATH, xpath)
        )
    )

def select_elements(xpath):
    return wait.until(
        EC.presence_of_all_elements_located(
            (By.XPATH, xpath)
        )
    )

def select_clickable_element(xpath):
    element = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH,  xpath)
        )
    )
    browser.execute_script("arguments[0].scrollIntoView(true);", element)
    element.click()
    sleep(5)
    return

def click(element):
    browser.execute_script("arguments[0].scrollIntoView(true);", element)
    element.click()
    sleep(5)
    return

def type(xpath, value):
    element = wait.until(
        EC.presence_of_all_elements_located(
            (By.XPATH, xpath)
        )
    )
    element.clear()
    for letter in value:
        element.send_keys(letter)
        sleep(0.4)
    sleep(5)
    return

def main():
    pass

log_in_with_phone_number_element = select_clickable_element("//div[contains(text(), 'Log in with phone number')]")
# click(log_in_with_phone_number_element)

country_dropdown_element = select_clickable_element("//button[.//span[contains(@data-icon, 'chevron')]]")
# click(country_dropdown_element)

country = 'Nigeria'

# country_search_element = select_element( "//p[contains(@class, 'selectable-text copyable-text')]")
type("//p[contains(@class, 'selectable-text copyable-text')]", country)

country_element = select_clickable_element( "(//button[contains(@aria-label, 'Selected country:')])[1]")
# click(country_element) #it used select_elements

phone_number = '8103882179'
# phone_number_element = select_element( "//input[contains(@aria-label, 'phone number')]")
type("//input[contains(@aria-label, 'phone number')]", phone_number)

next_element =select_clickable_element("(//button[.//div[contains(text(),'Next')]])[1]")
# click(next_element) #it used select_elements


link_code_element = select_element("(//div[contains(@aria-details, 'device-phone-number-code-screen')])[1]")
wait.until(lambda d: link_code_element.get_attribute('data-link-code') is not None)
link_code = link_code_element.get_attribute('data-link-code').replace(',', '').strip()
print("Link Code:", link_code)


try:
    contiune_element = select_clickable_element("//button[.//div[contains(text(), 'Continue')]]")
    # click(contiune_element)
finally:
    status_element = select_clickable_element("(//button[contains(@aria-label,'Status')])[1]")
    # click(status_element)

    add_status_element = select_clickable_element("(//button[contains(@aria-label,'Status')])[2]")
    # click(add_status_element)

    update_status_ul_element = select_elements("//div[contains(@role, 'application')]//ul")

    image_element = update_status_ul_element[0]
    # text_element = update_status_ul_element[1]

    click(image_element)

    file_path = r"C:\Users\HP\Desktop\Hotel\Juel\media\photos\2023\11\27\about4.jpg"
    pyautogui.write(file_path)
    pyautogui.press("enter")
    caption = 'room 1'
    # add_text_element = select_element("//div[@aria-label='Add a caption']//p[contains(@class,'selectable-text copyable-text')]")
    type("//div[@aria-label='Add a caption']//p[contains(@class,'selectable-text copyable-text')]", caption)

    add_file_element = select_clickable_element("//button[contains(@title, 'Add file')]")
    # click(add_file_element)

    file_path = r"C:\Users\HP\Desktop\Hotel\Juel\media\photos\2023\11\27\about4.jpg"
    pyautogui.write(file_path)
    pyautogui.press("enter")
    caption = 'room 2'
    # add_text_element = select_element("//div[@aria-label='Add a caption']//p[contains(@class,'selectable-text copyable-text')]")
    type("//div[@aria-label='Add a caption']//p[contains(@class,'selectable-text copyable-text')]", caption)

    send_element = select_clickable_element("//div[contains(@aria-label, 'Send')]")
    click(send_element)
input()
