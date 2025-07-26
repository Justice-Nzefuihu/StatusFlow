from time import sleep
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

def select_element(wait, xpath):
    return wait.until(EC.presence_of_element_located((By.XPATH, xpath)))

def select_clickable_element(wait, browser, xpath):
    element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
    browser.execute_script("arguments[0].scrollIntoView(true);", element)
    element.click()
    sleep(5)
    return element

def click(browser, element):
    browser.execute_script("arguments[0].scrollIntoView(true);", element)
    element.click()
    sleep(5)

def type_text(wait, xpath, value):
    element = select_element(wait, xpath)
    element.clear()
    for letter in value:
        element.send_keys(letter)
        sleep(0.1)
    sleep(2)