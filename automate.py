from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# 1. Initialize WebDriver
driver = webdriver.Chrome()
# Swagger UI ka URL
url = "http://127.0.0.1:8000/docs"

try:
    print("--- Starting Swagger UI Automation Test ---")
    driver.get(url)
    driver.maximize_window()
    time.sleep(3)

    # Step 1: Expand the 'POST /api/users' endpoint
    # Swagger UI mein users endpoint dhoondein aur click karein
    users_endpoint = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//span[text()='/api/users']"))
    )
    users_endpoint.click()
    time.sleep(2)

    # Step 2: Click 'Try it out'
    try_it_btn = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//button[text()='Try it out ']"))
    )
    try_it_btn.click()
    time.sleep(2)

    # Step 3: Enter the JSON payload with EXACTLY 8 characters password
    # Swagger UI ka text area dhoondein
    text_area = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "textarea"))
    )
    driver.execute_script("arguments[0].value = '';", text_area) # Clear

    payload = '''{
        "full_name": "Test User",
        "username": "testuser_boundary",
        "password": "Test1234", 
        "role": "Pharmacist",
        "email": "test@example.com"
    }'''
    # Note: "Test1234" exactly 8 characters ka hai
    
    text_area.send_keys(payload)
    time.sleep(1)

    # Step 4: Click 'Execute'
    execute_btn = driver.find_element(By.XPATH, "//button[text()='Execute']")
    execute_btn.click()
    time.sleep(3) # Wait for response

    # Step 5: Check the response code
    response_code_element = driver.find_element(By.XPATH, "//td[contains(text(), 'Code')]/following-sibling::td")
    response_code = response_code_element.text
    print(f"Response Code: {response_code}")

    # Expected Result: 200 (Success). Actual with Bug: 400 (Bad Request)
    if response_code == "200":
        print("Status: PASS -> 8-character password was accepted.")
    elif response_code == "400":
        print("Status: FAIL 🚨 -> 8-character password was rejected. Bug detected!")
    else:
        print(f"Status: FAIL 🚨 -> Unexpected response: {response_code}")

except Exception as e:
    print(f"An error occurred: {e}")

finally:
    time.sleep(3)
    driver.quit()