"""
LINKEDIN AUTO CONNECT 2025 by Sirat Wali - With Activity Logging
"""

import pandas as pd
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import *
import chromedriver_autoinstaller

chromedriver_autoinstaller.install()

# ===== Progress tracking variables for FastAPI =====
JOB_ID = None
JOBS = None

# ==================== CONFIG ====================
CSV_FILE = "file.csv"
OUTPUT_FILE = "results.csv"
EMAIL = "@gmail.com"
PASSWORD = ""
DAILY_LIMIT = 3
MAX_WAIT = 20

# ================================================

def log_activity(message):
    """Add message to activity log"""
    if JOBS and JOB_ID:
        if "activity_log" not in JOBS[JOB_ID]:
            JOBS[JOB_ID]["activity_log"] = []
        JOBS[JOB_ID]["activity_log"].append(message)
        print(f"[LOG] {message}")

def get_driver():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    service = Service(chromedriver_autoinstaller.install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => false});"
    })
    return driver

def random_sleep(min_sec=3, max_sec=8):
    time.sleep(random.uniform(min_sec, max_sec))

def login_linkedin(driver):
    log_activity("🔐 Logging into LinkedIn...")
    driver.get("https://www.linkedin.com/login")
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.ID, "username"))
    ).send_keys(EMAIL)
    driver.find_element(By.ID, "password").send_keys(PASSWORD + Keys.RETURN)
    random_sleep(5, 9)
    log_activity("✅ Login attempt finished")

def click_send_without_note(driver, wait):
    send_xpaths = [
        "//button[contains(@class,'artdeco-button--primary') and .//span[text()='Send without a note']]",
        "//button[.//span[text()='Send without a note']]//parent::button",
        "//button[@aria-label='Send without a note']",
        "//div[@role='dialog']//button[contains(@class,'artdeco-button--primary')]",
        "//button[contains(@class,'artdeco-modal__actionbar')]//button[1]"
    ]

    for xpath in send_xpaths:
        try:
            btn = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            driver.execute_script("arguments[0].click();", btn)
            log_activity("✅ Sent successfully!")
            return True
        except:
            continue

    log_activity("❌ Can't find Send button!")
    return False

def send_connection_request(driver):
    wait = WebDriverWait(driver, 15)
    driver.execute_script("window.scrollTo(0, 800);")
    time.sleep(0.6)

    # CASE 1: DIRECT "Connect" BUTTON
    direct_xpaths = [
        "//button[contains(@class,'artdeco-button--primary') and .//span[text()='Connect']]",
        "//button[.//span[text()='Connect'] and contains(@class,'artdeco-button--primary')]",
        "//button[contains(@class,'pv-top-card') and .//span[text()='Connect']]"
    ]

    for xpath in direct_xpaths:
        try:
            btn = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            time.sleep(0.6)
            driver.execute_script("arguments[0].click();", btn)
            log_activity("🔗 Direct Connect button clicked!")
            time.sleep(1)
            if click_send_without_note(driver, wait):
                random_sleep(4, 8)
                return True
            return False
        except:
            continue

    # CASE 2: "More" button method
    log_activity("🔍 Direct Connect not found, trying More button...")
    more_xpaths = [
        "//button[.//span[text()='More']]//parent::button",
        "//button[@aria-label='More actions']",
        "//button[contains(@class,'artdeco-button--secondary') and .//span[text()='More']]",
        "//div[contains(@class,'pvs-header')]//button[.//span[text()='More']]"
    ]

    for xpath in more_xpaths:
        try:
            more_btn = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            driver.execute_script("arguments[0].click();", more_btn)
            log_activity("⚙️ More button clicked successfully!")
            time.sleep(1)
            break
        except:
            continue
    else:
        log_activity("❌ More button not found")
        return False

    # Dropdown se Connect click
    connect_dropdown_xpaths = [
        "//span[text()='Connect']/ancestor::div[@role='button']",
        "//div[contains(@aria-label,'Invite') and contains(@aria-label,'to connect')]"
    ]

    for xpath in connect_dropdown_xpaths:
        try:
            connect_btn = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            driver.execute_script("arguments[0].click();", connect_btn)
            log_activity("🔗 Connect clicked through dropdown menu!")
            time.sleep(3)
            break
        except:
            continue
    else:
        log_activity("❌ Couldn't find Connect Button in Dropdown menu")
        return False

    return click_send_without_note(driver, wait)

def process_profile(driver, url, profile_number, total):
    log_activity(f"📍 Processing profile {profile_number}/{total}...")
    log_activity(f"🌐 Opening: {url}")
    driver.get(url)
    random_sleep(4, 8)
    driver.execute_script("window.scrollTo(0, 800);")
    time.sleep(0.6)

    if send_connection_request(driver):
        log_activity(f"✅ Profile {profile_number}/{total} - Sent successfully!")
        return "Sent"
    else:
        log_activity(f"❌ Profile {profile_number}/{total} - Failed")
        return "Failed"

def main():
    log_activity("🚀 LinkedIn Auto Connect Started by Sirat Wali")
    
    df = pd.read_csv(CSV_FILE)
    url_col = df.columns[0]
    urls = df[url_col].dropna().str.strip().tolist()

    if "status" not in df.columns:
        df["status"] = ""

    driver = get_driver()

    try:
        login_linkedin(driver)
        
        sent = 0
        total_profiles = len(urls)

        for index, url in enumerate(urls, 1):
            if sent >= DAILY_LIMIT:
                log_activity(f"⏹️ Daily limit {DAILY_LIMIT} reached!")
                break

            if df.loc[df[url_col] == url, "status"].iloc[0] == "Sent":
                log_activity(f"⏭️ Profile {index}/{total_profiles} - Already sent, skipping")
                continue

            status = process_profile(driver, url, index, total_profiles)

            df.loc[df[url_col] == url, "status"] = status
            df.to_csv(OUTPUT_FILE, index=False)

            if status == "Sent":
                sent += 1

            # Update progress
            if JOBS and JOB_ID:
                JOBS[JOB_ID]["done"] = sent

        log_activity(f"📊 Task Summary: Total {sent} connections sent out of {total_profiles}")
        log_activity(f"✨ Successfully Task Completed! Total {sent} connections sent")

        # Mark job completed
        if JOBS and JOB_ID:
            JOBS[JOB_ID]["status"] = "completed"
            JOBS[JOB_ID]["result_file"] = OUTPUT_FILE

    except Exception as e:
        log_activity(f"❌ Error Occurred: {str(e)}")
        print("Error Occurred", e)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()