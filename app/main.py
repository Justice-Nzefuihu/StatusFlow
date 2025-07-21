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
wait = WebDriverWait(browser, timeout=30)
sleep(10)

log_in_with_phone_number_element = wait.until(
    EC.presence_of_element_located(
        (By.XPATH, "//div[contains(text(), 'Log in with phone number')]")
        )
    )
browser.execute_script("arguments[0].scrollIntoView(true);", log_in_with_phone_number_element)
log_in_with_phone_number_element.click()
sleep(10)


country_dropdown_element = wait.until(
    EC.presence_of_element_located(
        (By.XPATH, "//button[.//span[contains(@data-icon, 'chevron')]]")
        )
    )
browser.execute_script("arguments[0].scrollIntoView(true);", country_dropdown_element)
country_dropdown_element.click()

country = 'Nigeria'

country_search_element = wait.until(
    EC.presence_of_element_located(
        (By.XPATH, "//p[contains(@class, 'selectable-text copyable-text')]")
    )
)
country_search_element.clear()
country_search_element.send_keys(country)
sleep(10)

country_element = wait.until(
    EC.presence_of_all_elements_located(
        (By.XPATH, "//button[contains(@aria-label, 'Selected country:')]")
    )
)[0]
browser.execute_script("arguments[0].scrollIntoView(true);", country_element)
country_element.click()
sleep(10)

phone_number = '8103882179'
log_in_with_phone_number_element = wait.until(
    EC.presence_of_element_located(
        (By.XPATH, "//input[contains(@aria-label, 'phone number')]")
    )
)
log_in_with_phone_number_element.clear()
log_in_with_phone_number_element.send_keys(phone_number)
sleep(10)

next_element = wait.until(
    EC.presence_of_all_elements_located(
        (By.XPATH, "//button[.//div[contains(text(),'Next')]]")
    )
)[0]
browser.execute_script("arguments[0].scrollIntoView(true);", next_element)
next_element.click()
sleep(10)

link_code_element = wait.until(
    EC.presence_of_element_located(
        (By.XPATH, "(//div[contains(@aria-details, 'device-phone-number-code-screen')])[1]")
    )
)
wait.until(lambda d: link_code_element.get_attribute('data-link-code') is not None)
link_code = link_code_element.get_attribute('data-link-code').strip(',')
print("Link Code:", link_code)


try:
    contiune_element = wait.until(
        EC.presence_of_element_located(
            (By.XPATH, "//button[.//div[contains(text(), 'Continue')]]")
        )
    )
    browser.execute_script("arguments[0].scrollIntoView(true);", contiune_element)
    contiune_element.click()
    sleep(10)
finally:
    status_element = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH,  "(//button[contains(@aria-label,'Status')])[1]")
        )
    )
    browser.execute_script("arguments[0].scrollIntoView(true);", status_element)
    status_element.click()
    sleep(10)

    add_status_element = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH,  "(//button[contains(@aria-label,'Status')])[2]")
        )
    )
    browser.execute_script("arguments[0].scrollIntoView(true);", add_status_element)
    add_status_element.click()
    sleep(10)

    update_status_ul_element = wait.until(
        EC.presence_of_all_elements_located(
            (By.XPATH, "//div[contains(@role, 'application')]//ul")
        )
    )
    image_element = update_status_ul_element[0]
    text_element = update_status_ul_element[1]
    browser.execute_script("arguments[0].scrollIntoView(true);", image_element)
    image_element.click()

    file_path = r"C:\Users\HP\Desktop\Hotel\Juel\media\photos\2023\11\27\about4.jpg"
    pyautogui.write(file_path)
    pyautogui.press("enter")
    caption = 'room 1'
    add_text_element = wait.until(
        EC.presence_of_element_located(
            (By.XPATH, "//div[@aria-label='Add a caption']//p[contains(@class,'selectable-text copyable-text')]")
        )
    )
    add_text_element.clear()
    add_text_element.send_keys(caption)

    send_element = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH,  "//div[contains(@aria-label, 'Send')]")
        )
    )

    add_file_element = wait.until(
        EC.presence_of_element_located(
            (By.XPATH, "//button[contains(@title, 'Add file')]")
        )
    )

    browser.execute_script("arguments[0].scrollIntoView(true);", send_element)
    send_element.click()
    sleep(10)
input()
