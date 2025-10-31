#!/usr/bin/env python3

import streamlit as st
import time
import threading
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
import os
import sqlite3
import hashlib
import json
from datetime import datetime
import subprocess
import sys
import random 
import re
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException, ElementNotInteractableException

# --- GitHub Configuration (UPDATED) ---
GITHUB_REPO_OWNER = "KHUSI223"
GITHUB_REPO_NAME = "MISS-KHUSHI"
GITHUB_BRANCH = "main" 
GITHUB_HINDI_FILE = "Hindi.txt"
GITHUB_ENGLISH_FILE = "EmojiMath.txt"

# --- Database and Auth Functions ---

def init_db():
    """Initialize database with proper error handling"""
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,  
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_configs (
                user_id INTEGER PRIMARY KEY,
                chat_id TEXT,
                name_prefix TEXT,
                delay INTEGER DEFAULT 10,
                cookies TEXT,
                messages TEXT,
                automation_running BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                message_source TEXT DEFAULT 'Direct Text Area',
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Check and add message_source column if missing
        try:
            c.execute("SELECT message_source FROM user_configs LIMIT 1")
        except sqlite3.OperationalError:
            c.execute("ALTER TABLE user_configs ADD COLUMN message_source TEXT DEFAULT 'Direct Text Area'")
            
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Database initialization error: {e}")
        return False

def hash_password(password):
    """Hash password securely"""
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, password):
    """Create new user with proper validation"""
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('SELECT id FROM users WHERE username = ?', (username,))
        if c.fetchone(): 
            return False, "Username already exists"
        
        password_hash = hash_password(password)
        c.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', 
                 (username, password_hash))
        user_id = c.lastrowid
        
        # Create default configuration
        c.execute('''
            INSERT INTO user_configs 
            (user_id, chat_id, name_prefix, delay, cookies, messages, message_source) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, '', '[MR SHARABI]', 10, '', 'Hello!\nHow are you?', 'Direct Text Area'))
        
        conn.commit()
        conn.close()
        return True, "User created successfully"
    except Exception as e:
        return False, f"Error creating user: {str(e)}"

def verify_user(username, password):
    """Verify user credentials"""
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        password_hash = hash_password(password)
        c.execute('SELECT id FROM users WHERE username = ? AND password_hash = ?', 
                 (username, password_hash))
        result = c.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        print(f"Verify user error: {e}")
        return None

def get_user_config(user_id):
    """Get user configuration with defaults"""
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('''
            SELECT chat_id, name_prefix, delay, cookies, messages, message_source
            FROM user_configs WHERE user_id = ?
        ''', (user_id,))
        result = c.fetchone()
        conn.close()
        
        if result:
            return {
                'chat_id': result[0] or '',
                'name_prefix': result[1] or '[MR SHARABI]',
                'delay': result[2] if result[2] is not None else 10,
                'cookies': result[3] or '',
                'messages': result[4] or 'Hello!\nHow are you?',
                'message_source': result[5] or 'Direct Text Area'
            }
        return None
    except Exception as e:
        print(f"Get user config error: {e}")
        return None

def update_user_config(user_id, chat_id, name_prefix, delay, cookies, messages, message_source):
    """Update user configuration"""
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO user_configs 
            (user_id, chat_id, name_prefix, delay, cookies, messages, message_source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, chat_id, name_prefix, delay, cookies, messages, message_source))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Update user config error: {e}")
        return False

def get_automation_running(user_id):
    """Check if automation is running"""
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('SELECT automation_running FROM user_configs WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else False
    except Exception as e:
        print(f"Get automation running error: {e}")
        return False

def set_automation_running(user_id, running):
    """Set automation running status"""
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('UPDATE user_configs SET automation_running = ? WHERE user_id = ?', 
                 (running, user_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Set automation running error: {e}")
        return False

def get_username(user_id):
    """Get username from user ID"""
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('SELECT username FROM users WHERE id = ?', (user_id,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else "Unknown"
    except Exception as e:
        print(f"Get username error: {e}")
        return "Unknown"

# Initialize database
init_db()

# --- FIXED GITHUB FETCHING FUNCTION - HINDI MATRA ISSUE SOLVED ---
def fetch_messages_from_github(file_name, automation_state=None):
    """Fetches and properly processes messages from GitHub with UNICODE FIX for Hindi"""
    
    raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/{GITHUB_BRANCH}/{file_name}"
               
    log_message(f'📡 Fetching messages from: {file_name}', automation_state)
    
    try:
        response = requests.get(raw_url, timeout=15)
        
        if response.status_code == 200:
            # ✅ FIX 1: HINDI MATRA ISSUE - Use proper encoding
            response.encoding = 'utf-8'  # Force UTF-8 encoding
            content = response.text.strip()
            
            if not content:
                log_message(f'❌ File {file_name} is empty', automation_state, log_type='error')
                return None
            
            # IMPROVED PROCESSING WITH UNICODE SUPPORT
            messages = []
            lines = content.split('\n')
            valid_lines_found = 0
            
            for line_num, line in enumerate(lines, 1):
                original_line = line
                line = line.strip()
                
                # Skip empty lines and comments
                if not line:
                    continue
                if line.startswith('#') or line.startswith('//') or line.startswith('/*') or line.startswith('--'):
                    continue
                
                # ✅ FIX 2: PRESERVE HINDI CHARACTERS - No aggressive cleaning
                clean_message = line
                
                # Handle format: number|message
                if '|' in line:
                    parts = line.split('|', 1)
                    if len(parts) > 1 and parts[1].strip():
                        clean_message = parts[1].strip()
                    else:
                        clean_message = parts[0].strip()
                
                # Handle format: message (with possible numbering)
                elif re.match(r'^\d+[\.\)]\s*', clean_message):
                    clean_message = re.sub(r'^\d+[\.\)]\s*', '', clean_message)
                
                # ✅ FIX 3: KEEP ALL UNICODE CHARACTERS - Don't remove Hindi matras
                # Only remove actual unwanted characters, preserve Hindi
                clean_message = re.sub(r'[^\w\s\.\?\!\,\@\#\$\&\*\(\)\-\+\=\[\]\{\}\:\;\"\'à-ÿÀ-ßā-žअ-ॿ०-९॰-]+', '', clean_message)
                
                # Only add non-empty messages
                if clean_message and len(clean_message.strip()) > 0:
                    messages.append(clean_message.strip())
                    valid_lines_found += 1
            
            if valid_lines_found == 0:
                log_message(f'❌ No valid messages found in {file_name}', automation_state, log_type='error')
                return None
            
            log_message(f'✅ Successfully loaded {len(messages)} messages from {file_name}', automation_state, log_type='success')
            
            # Show sample of loaded messages for verification WITH HINDI
            sample_count = min(3, len(messages))
            for i in range(sample_count):
                log_message(f'📝 Sample {i+1}: {messages[i][:60]}...', automation_state)
                
            return messages
            
        else:
            log_message(f'❌ GitHub fetch failed. Status: {response.status_code}', automation_state, log_type='error')
            return None
            
    except requests.exceptions.Timeout:
        log_message(f'❌ GitHub request timeout for {file_name}', automation_state, log_type='error')
        return None
    except requests.exceptions.ConnectionError:
        log_message(f'❌ Network connection error for {file_name}', automation_state, log_type='error')
        return None
    except Exception as e:
        log_message(f'❌ Unexpected error fetching {file_name}: {str(e)}', automation_state, log_type='error')
        return None

# --- FIXED LOG FUNCTION WITH CONTROLLED SPEED ---
def log_message(msg, automation_state=None, log_type='info'):
    """Real-time logs with PERFECT SPEED CONTROL for readability"""
    timestamp = time.strftime("%H:%M:%S")
    formatted_msg = f"[{timestamp}] {msg}"
    
    # Add appropriate styling
    if log_type == 'error':
        formatted_msg = f'<span class="error-log">❌ {formatted_msg}</span>'
    elif log_type == 'success':
        formatted_msg = f'<span class="success-log">✅ {formatted_msg}</span>'
    elif log_type == 'critical':
        formatted_msg = f'<span class="critical-log">🚨 {formatted_msg}</span>'
    else:
        formatted_msg = f'<span class="info-log">📝 {formatted_msg}</span>'
    
    print(f"LOG: {formatted_msg}")
    
    # ✅ FIX 3: PERFECT LOG SPEED - Optimized delays
    if automation_state and automation_state.running:
        # Different delays based on log type
        if log_type == 'critical':
            time.sleep(1.5)  # Important messages get more time
        elif log_type == 'success':
            time.sleep(1.2)  # Success messages moderate time
        else:
            time.sleep(0.8)  # Normal info messages
    
    if automation_state:
        automation_state.logs.append(formatted_msg)
        automation_state.last_log_time = time.time()
    else:
        if 'logs' in st.session_state:
            st.session_state.logs.append(formatted_msg)

# --- Streamlit UI Configuration ---
st.set_page_config(
    page_title="MR SHARABI END TO END FACEBOOK CONVO",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ✅ FIXED CSS WITH KEYBOARD FIXES AND INSTANT SAVE OPTIMIZATION
custom_css = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');
    
    * { font-family: 'Poppins', sans-serif; }
    
    .main-header {
        background: linear-gradient(135deg, #764ba2 0%, #d62828 100%);
        padding: 2rem;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px rgba(214, 40, 40, 0.4);
        position: relative;
        overflow: hidden;
    }
    
    .profile-section {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 10px;
        margin-bottom: 15px;
    }
    
    .profile-pic {
        width: 80px;  
        height: 80px; 
        border-radius: 50%;
        border: 3px solid white;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        margin-bottom: 5px;
    }
    
    .profile-name {
        color: white;
        font-size: 2rem; 
        font-weight: 700;
        text-shadow: 2px 2px 6px rgba(0,0,0,0.5);
        margin-top: 5px;
    }
    
    .main-header h1 {
        color: white;
        font-size: 2.2rem;
        font-weight: 700;
        margin: 5px 0 0 0;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.4);
    }
    
    .main-header p {
        color: rgba(255,255,255,0.9);
        font-size: 1.1rem;
        margin-top: 0.5rem;
    }
    
    /* ✅ FIXED INPUT STYLING WITH KEYBOARD PROTECTION */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stNumberInput > div > div > input {
        border: 2px solid #e0e0e0 !important;
        border-radius: 8px !important;
        padding: 12px 16px !important;
        font-size: 16px !important;
        transition: all 0.2s ease !important;
        background: white !important;
        box-shadow: none !important;
        caret-color: auto !important;
        user-select: text !important;
        -webkit-user-select: text !important;
        touch-action: manipulation !important;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus,
    .stNumberInput > div > div > input:focus {
        border-color: #d62828 !important;
        box-shadow: 0 0 0 3px rgba(214, 40, 40, 0.1) !important;
        outline: none !important;
    }
    
    /* Sharabi Button Styling */
    .sharabi-btn button {
        background: linear-gradient(135deg, #d62828 0%, #ff6b6b 100%);
        color: white;
        border: none;
        border-radius: 12px !important;
        padding: 0.75rem 2rem;
        font-weight: 700 !important;
        font-size: 1.2rem !important;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(214, 40, 40, 0.5);
        letter-spacing: 1px;
    }
    
    .sharabi-btn button:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(214, 40, 40, 0.8);
    }
    
    .log-container {
        background: #1e1e1e;
        color: #e0e0e0; 
        padding: 1rem;
        border-radius: 10px;
        font-family: 'Courier New', monospace;
        max-height: 400px;
        overflow-y: auto;
        border: 1px solid #333;
        font-size: 14px;
        line-height: 1.4;
    }
    
    .status-running { color: #00ff00; font-weight: bold; font-size: 18px; }
    .status-stopped { color: #ff4444; font-weight: bold; font-size: 18px; }
    
    .success-log { color: #00ff00; }
    .error-log { color: #ff5555; }
    .info-log { color: #e0e0e0; }
    .critical-log { color: #ffff00; font-weight: bold; }
    
    /* Fixed Radio Button Styling */
    div[data-testid="stRadio"] > label {
        font-weight: 600;
        margin-bottom: 10px;
    }
    
    div[data-testid="stRadio"] > div {
        flex-direction: row !important;
        gap: 20px !important;
        justify-content: center !important;
    }
    
    div[data-testid="stRadio"] > div > label {
        background: #f0f0f5 !important;
        padding: 10px 20px !important;
        border-radius: 20px !important;
        border: 2px solid #ddd !important;
        transition: all 0.3s ease !important;
    }
    
    div[data-testid="stRadio"] > div > label[data-testid="stRadioLabel"]:has(input:checked) {
        background: linear-gradient(135deg, #764ba2 0%, #d62828 100%) !important;
        color: white !important;
        border-color: #d62828 !important;
        box-shadow: 0 4px 15px rgba(214, 40, 40, 0.3) !important;
    }

    .main-content-box { background: #e6f7ff; padding: 1.5rem; border-radius: 10px; border: 1px solid #cceeff; margin-bottom: 1rem; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); }
    .config-box { 
        background: #fff0f6;
        padding: 1.5rem; 
        border-radius: 10px; 
        border: 1px solid #ffdae9; 
        margin-bottom: 1rem; 
        box-shadow: 0 2px 8px rgba(255, 105, 180, 0.1);
    }
    .automation-box { 
        background: #f0fff4;
        padding: 1.5rem; 
        border-radius: 10px; 
        border: 1px solid #d0f0c0; 
        box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
    }
    
    .footer {
        text-align: center;
        margin-top: 2rem;
        padding: 10px;
        font-size: 0.85rem;
        color: #888;
        border-top: 1px solid #eee;
    }
    
    .np-info-box {
        background: #f8f9fa;
        border-left: 4px solid #d62828;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
    }
    
    /* ✅ FIX: ULTRA FAST INSTANT SAVE BUTTON STYLING */
    .instant-save-btn button {
        background: linear-gradient(135deg, #28a745 0%, #20c997 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.5rem 1.5rem !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }
    
    .instant-save-btn button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(40, 167, 69, 0.4) !important;
    }
    
    .instant-save-btn button:active {
        transform: translateY(0) !important;
        transition: all 0.1s ease !important;
    }
    
    /* ✅ KEYBOARD FIX: Prevent Streamlit from stealing focus */
    div[data-testid="stVerticalBlock"] {
        pointer-events: auto !important;
    }
    
    /* Better touch handling for mobile */
    .stTextArea > div > div > textarea {
        touch-action: manipulation !important;
        -webkit-touch-callout: default !important;
    }
    
    /* Save status animation */
    .save-status {
        animation: fadeInOut 3s ease-in-out;
    }
    
    @keyframes fadeInOut {
        0% { opacity: 0; }
        20% { opacity: 1; }
        80% { opacity: 1; }
        100% { opacity: 0; }
    }
</style>
"""

st.markdown(custom_css, unsafe_allow_html=True)

# --- COMPREHENSIVE SESSION STATE INITIALIZATION ---
if 'logged_in' not in st.session_state: 
    st.session_state.logged_in = False

if 'user_id' not in st.session_state: 
    st.session_state.user_id = None

if 'username' not in st.session_state: 
    st.session_state.username = None

if 'automation_running' not in st.session_state: 
    st.session_state.automation_running = False

if 'logs' not in st.session_state: 
    st.session_state.logs = []

if 'message_count' not in st.session_state: 
    st.session_state.message_count = 0

if 'last_log_count' not in st.session_state: 
    st.session_state.last_log_count = 0

if 'auto_refresh' not in st.session_state: 
    st.session_state.auto_refresh = False

if 'config_initialized' not in st.session_state: 
    st.session_state.config_initialized = False

if 'config_chat_id' not in st.session_state: 
    st.session_state.config_chat_id = ''

if 'config_name_prefix' not in st.session_state: 
    st.session_state.config_name_prefix = '[MR SHARABI]'

if 'config_delay' not in st.session_state: 
    st.session_state.config_delay = 10

if 'config_messages' not in st.session_state: 
    st.session_state.config_messages = 'Hello!\nHow are you?'

if 'config_cookies' not in st.session_state: 
    st.session_state.config_cookies = ''

if 'config_message_source' not in st.session_state: 
    st.session_state.config_message_source = 'Direct Text Area'

if 'last_action_status' not in st.session_state: 
    st.session_state.last_action_status = None

if 'last_action_type' not in st.session_state: 
    st.session_state.last_action_type = None

if 'auto_start_checked' not in st.session_state: 
    st.session_state.auto_start_checked = False

if 'github_test_result' not in st.session_state: 
    st.session_state.github_test_result = None

if 'github_test_messages' not in st.session_state: 
    st.session_state.github_test_messages = None

# ✅ FIX: INSTANT SAVE STATE
if 'config_saved' not in st.session_state:
    st.session_state.config_saved = False

if 'save_clicked' not in st.session_state:
    st.session_state.save_clicked = False

if 'last_save_time' not in st.session_state:
    st.session_state.last_save_time = 0

class AutomationState:
    def __init__(self):
        self.running = False
        self.message_count = 0
        self.logs = []
        self.message_rotation_index = 0
        self.last_log_time = 0
        self.thread_lock = threading.Lock()
        # ✅ FIX: IMMEDIATE LOGS FLAG
        self.immediate_logs_started = False

if 'automation_state' not in st.session_state:
    st.session_state.automation_state = AutomationState()

# --- IMPROVED SELENIUM AUTOMATION FUNCTIONS ---

def setup_browser(automation_state=None):
    """Initializes the browser with COMPREHENSIVE path handling"""
    log_message('STEP 1: Setting up Chrome browser...', automation_state, log_type='critical')
    
    chrome_options = Options()
    
    # Standard Streamlit Headless Setup
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--remote-debugging-port=9222')
    chrome_options.add_argument('--window-size=1920,1080')
    
    # ADDED FOR BETTER PERFORMANCE
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--disable-background-timer-throttling')
    chrome_options.add_argument('--disable-renderer-backgrounding')
    chrome_options.add_argument('--disable-backgrounding-occluded-windows')
    
    # Stealth Configuration
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument('--disable-blink-features=AutomationControlled') 
    chrome_options.add_argument('--disable-features=AutomationCommandLine') 
    chrome_options.add_argument('--disable-logging') 
    chrome_options.add_argument('--log-level=3') 
    
    # COMPREHENSIVE PATH HANDLING
    possible_chrome_paths = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser", 
        "/usr/bin/google-chrome",
        "/usr/bin/chrome",
        "/usr/local/bin/chromium",
        "/usr/local/bin/chromium-browser",
        "/usr/local/bin/google-chrome",
        "/snap/bin/chromium"
    ]
    
    possible_chromedriver_paths = [
        "/usr/bin/chromedriver",
        "/usr/local/bin/chromedriver",
        "/usr/lib/chromium-browser/chromedriver",
        "/snap/bin/chromium.chromedriver"
    ]
    
    CHROME_PATH = None
    CHROMEDRIVER_PATH = None
    
    # Find existing Chrome path
    for path in possible_chrome_paths:
        if os.path.exists(path):
            CHROME_PATH = path
            log_message(f'Found Chrome at: {path}', automation_state)
            break
    
    # Find existing ChromeDriver path  
    for path in possible_chromedriver_paths:
        if os.path.exists(path):
            CHROMEDRIVER_PATH = path
            log_message(f'Found ChromeDriver at: {path}', automation_state)
            break
    
    driver = None
    
    try:
        if not CHROMEDRIVER_PATH:
            log_message('ChromeDriver not found in standard locations', automation_state, log_type='error')
            raise FileNotFoundError("ChromeDriver not found or accessible.")
            
        service = Service(CHROMEDRIVER_PATH)
        if CHROME_PATH:
            chrome_options.binary_location = CHROME_PATH
            log_message(f'Using Chrome at: {CHROME_PATH}', automation_state)
        else:
            log_message('Using system default Chrome', automation_state)
            
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Stealth Payload
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_script("""
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
            window.chrome = { runtime: {} };
        """)
        log_message('Stealth payload injected', automation_state, log_type='critical')
        
        log_message('Browser ready!', automation_state, log_type='success')
        return driver
        
    except WebDriverException as e:
        log_message(f'Browser setup FAILED (WebDriver): {type(e).__name__}: {str(e)[:80]}', automation_state, log_type='error')
        raise ConnectionError("Browser setup failed due to WebDriver issue.")
    except FileNotFoundError as e:
        raise ConnectionError(f"Browser setup failed: {str(e)}")
    except Exception as e:
        log_message(f'Browser setup FAILED (General): {type(e).__name__}: {str(e)[:80]}', automation_state, log_type='error')
        raise ConnectionError("Browser setup failed due to unknown issue.")

def find_message_input(driver, process_id, automation_state=None):
    """Find message input with multiple fallback strategies"""
    log_message(f'{process_id}: Finding message input...', automation_state, log_type='critical')
    
    try:
        # Scrolling to ensure elements are visible
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
    except Exception:
        pass
    
    message_input_selectors = [
        'div[role="textbox"][contenteditable="true"]', 
        'div[data-lexical-editor="true"]',
        'div[aria-label*="message" i][contenteditable="true"]', 
        'div[contenteditable="true"]', 
        'div[aria-label*="Type a message" i]',
        'div[data-lexical-editor="true"][contenteditable="true"]'
    ]
    
    for idx, selector in enumerate(message_input_selectors):
        try:
            log_message(f'{process_id}: Trying selector {idx+1}...', automation_state)
            wait = WebDriverWait(driver, 12)
            
            element = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )

            # Additional validation
            is_editable = driver.execute_script("return arguments[0].contentEditable === 'true';", element)

            if is_editable and element.is_displayed() and element.is_enabled():
                log_message(f'{process_id}: Input found with selector {idx+1}!', automation_state, log_type='success')
                driver.execute_script("arguments[0].click();", element)
                time.sleep(2)
                return element
            
        except TimeoutException:
            continue
        except (NoSuchElementException, ElementNotInteractableException):
            continue
        except Exception as e:
            log_message(f'{process_id}: Selector {idx+1} failed: {str(e)[:50]}', automation_state)
            continue
    
    log_message(f'{process_id}: Message input not found with any selector!', automation_state, log_type='error')
    return None

def get_next_message(messages, automation_state=None):
    """Proper message rotation with bounds checking"""
    if not messages or len(messages) == 0:
        return 'Hello!'
    
    if automation_state:
        # Ensure index stays within bounds
        current_index = automation_state.message_rotation_index % len(messages)
        message = messages[current_index]
        automation_state.message_rotation_index += 1
        
        # Reset index if it becomes too large (prevent overflow)
        if automation_state.message_rotation_index >= 10000:
            automation_state.message_rotation_index = 0
            
        return message
    else:
        return messages[0] if messages else 'Hello!'

def check_message_sent_simple(driver, process_id, message_to_send, automation_state=None):
    """Simple verification without breaking automation"""
    try:
        time.sleep(3)
        # Check if the input area is still present and empty
        message_inputs = driver.find_elements(By.CSS_SELECTOR, 'div[role="textbox"][contenteditable="true"]')
        if message_inputs:
            log_message(f'{process_id}: Message delivery attempt complete.', automation_state, log_type='success')
            return True
        else:
            log_message(f'{process_id}: Continuing to next message...', automation_state)
            return True
            
    except Exception as e:
        log_message(f'{process_id}: Continuing despite verification issue: {type(e).__name__}', automation_state)
        return True

def simulate_human_activity(driver, process_id, automation_state=None):
    """Randomly scrolls the page simulating human behavior"""
    scroll_amount = random.randint(150, 400)
    scroll_direction = random.choice(['up', 'down'])
    
    try:
        if scroll_direction == 'down':
            driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            log_message(f'{process_id}: Scrolled down {scroll_amount}px', automation_state)
        else:
            driver.execute_script(f"window.scrollBy(0, -{scroll_amount});")
            log_message(f'{process_id}: Scrolled up {scroll_amount}px', automation_state)
        
        time.sleep(random.uniform(1.5, 3.5))
    except WebDriverException as e:
        log_message(f'{process_id}: Scroll failed: {type(e).__name__}', automation_state, log_type='error')
        time.sleep(1)

def simple_send_message(driver, message_input, message, process_id, automation_state=None):
    """Clean and simple message sending with HINDI MATRA FIX"""
    try:
        # Check if element is still valid
        if not message_input.is_displayed() or not message_input.is_enabled():
            log_message(f'{process_id}: Input element lost/disabled before send.', automation_state, log_type='critical')
            return False

        # Clear existing text
        message_input.clear()
        time.sleep(1)
        
        # ✅ FIX 1: HINDI MATRA PRESERVATION - Minimal cleaning
        # Only remove truly harmful characters, preserve Hindi completely
        clean_message = re.sub(r'[^\w\s\.\?\!\,\@\#\$\&\*\(\)\-\+\=\[\]\{\}\:\;\"\'à-ÿÀ-ßā-žअ-ॿ०-९॰-]+', '', message)
        
        if not clean_message.strip():
            clean_message = "Hello"
            
        log_message(f'{process_id}: Typing message: {clean_message[:50]}...', automation_state)
        
        # Type message like human with random delays
        for char in clean_message:
            message_input.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))  # Random typing speed
        
        time.sleep(1)
        
        # Send with Enter key
        log_message(f'{process_id}: Sending message...', automation_state)
        message_input.send_keys(Keys.ENTER)
        
        return True
    except WebDriverException as e:
        log_message(f'{process_id}: Send failed (Browser error): {type(e).__name__}', automation_state, log_type='error')
        return False
    except Exception as e:
        log_message(f'{process_id}: Send failed (General error): {type(e).__name__}', automation_state, log_type='error')
        return False

# --- FIXED SEND MESSAGES FUNCTION ---
def send_messages(config, automation_state, user_id, process_id='AUTO-1'):
    driver = None
    messages_sent = 0
    
    # ✅ FIX 3: IMMEDIATE LOGS - Start showing logs immediately
    if not automation_state.immediate_logs_started:
        automation_state.immediate_logs_started = True
        log_message(f'{process_id}: 🚀 AUTOMATION STARTING IMMEDIATELY...', automation_state, log_type='critical')
        time.sleep(1.5)
        log_message(f'{process_id}: Initializing systems...', automation_state, log_type='critical')
        time.sleep(1.2)
    
    try:
        # 1. Setup Browser 
        log_message(f'{process_id}: Starting automation for User {user_id}...', automation_state)
        driver = setup_browser(automation_state)
        
        # 2. Navigate to Facebook 
        log_message(f'{process_id}: Navigating to Facebook...', automation_state)
        driver.get('https://www.facebook.com/')
        log_message(f'{process_id}: Facebook loaded', automation_state, log_type='success')
            
        time.sleep(4)
        
        # 3. Add Cookies
        if config['cookies'] and config['cookies'].strip():
            log_message(f'{process_id}: Adding cookies...', automation_state)
            cookie_array = config['cookies'].split(';')
            cookies_added = 0
            for cookie in cookie_array:
                cookie_trimmed = cookie.strip()
                if cookie_trimmed:
                    first_equal_index = cookie_trimmed.find('=')
                    if first_equal_index > 0:
                        name = cookie_trimmed[:first_equal_index].strip()
                        value = cookie_trimmed[first_equal_index + 1:].strip()
                        try:
                            driver.add_cookie({
                                'name': name,
                                'value': value,
                                'domain': '.facebook.com',
                                'path': '/'
                            })
                            cookies_added += 1
                        except Exception as e:
                            log_message(f'{process_id}: Cookie add failed: {name}', automation_state, log_type='error')
                            pass
            log_message(f'{process_id}: Added {cookies_added} cookies', automation_state, log_type='success')
        
        # 4. Navigate to Chat 
        if config['chat_id']:
            chat_id = config['chat_id'].strip()
            log_message(f'{process_id}: Opening conversation...', automation_state)
            driver.get(f'https://www.facebook.com/messages/e2ee/t/{chat_id}')
            log_message(f'{process_id}: Conversation loaded', automation_state, log_type='success')
        else:
            log_message(f'{process_id}: Chat ID not provided. Cannot proceed.', automation_state, log_type='critical')
            automation_state.running = False
            return 0
        
        # 5. Wait for Page Load 
        log_message(f'{process_id}: Waiting for page to load...', automation_state, log_type='critical')
        try:
            wait = WebDriverWait(driver, 30)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            log_message(f'{process_id}: Page ready', automation_state, log_type='success')
        except TimeoutException:
            log_message(f'{process_id}: Page load timeout. Continuing...', automation_state, log_type='critical')
        
        time.sleep(5)
        
        # 6. Find Message Input 
        message_input = find_message_input(driver, process_id, automation_state)
        
        if not message_input:
            log_message(f'{process_id}: Message input not found, stopping.', automation_state, log_type='critical')
            automation_state.running = False
            return 0
        
        log_message(f'{process_id}: Ready to send messages!', automation_state, log_type='success')
        
        # 7. FIXED MESSAGE SOURCE LOGIC
        delay = int(config['delay'])
        message_source = config.get('message_source', 'Direct Text Area')
        messages_list = []

        log_message(f'{process_id}: Selected message source: {message_source}', automation_state, log_type='critical')

        if message_source == 'SHARABI HINDI NP':
            github_messages = fetch_messages_from_github(GITHUB_HINDI_FILE, automation_state)
            if github_messages:
                messages_list = github_messages
                log_message(f'{process_id}: ✅ Using {len(messages_list)} messages from SHARABI HINDI NP', automation_state, log_type='success')
            else:
                messages_list = [msg.strip() for msg in config['messages'].split('\n') if msg.strip()]
                log_message(f'{process_id}: ❌ GitHub fetch failed, using direct messages', automation_state, log_type='critical')
                
        elif message_source == 'SHARABI ENGLISH NP':
            github_messages = fetch_messages_from_github(GITHUB_ENGLISH_FILE, automation_state)
            if github_messages:
                messages_list = github_messages
                log_message(f'{process_id}: ✅ Using {len(messages_list)} messages from SHARABI ENGLISH NP', automation_state, log_type='success')
            else:
                messages_list = [msg.strip() for msg in config['messages'].split('\n') if msg.strip()]
                log_message(f'{process_id}: ❌ GitHub fetch failed, using direct messages', automation_state, log_type='critical')
                
        else: # 'Direct Text Area'
            messages_list = [msg.strip() for msg in config['messages'].split('\n') if msg.strip()]
            log_message(f'{process_id}: ✅ Using {len(messages_list)} messages from Direct Text Area', automation_state, log_type='success')
            
        if not messages_list: 
            messages_list = ['Hello!', 'How are you?', 'This is automated']
            log_message(f'{process_id}: ⚠️ No messages found, using defaults', automation_state, log_type='critical')

        log_message(f'{process_id}: 🎯 FINAL - Total messages loaded: {len(messages_list)}', automation_state, log_type='success')
        
        # 8. CONTINUOUS MESSAGE SENDING LOOP 
        while automation_state.running:
            
            base_message = get_next_message(messages_list, automation_state)
            
            # FIXED MESSAGE PREFIX
            name_prefix = config.get('name_prefix', '')
            if name_prefix and isinstance(name_prefix, str) and name_prefix.strip():
                message_to_send = f"{name_prefix.strip()} {base_message}"
            else:
                message_to_send = base_message
            
            log_message(f'{process_id}: Sending message {messages_sent+1}...', automation_state)
            
            try:
                # Re-find input element periodically
                if messages_sent > 0 and messages_sent % 10 == 0:
                     log_message(f'{process_id}: Re-locating input element...', automation_state)
                     message_input = find_message_input(driver, process_id, automation_state)
                     if not message_input:
                         raise ElementNotInteractableException("Input element lost in loop.")
                         
                send_success = simple_send_message(driver, message_input, message_to_send, process_id, automation_state)
                
                if send_success:
                    is_delivered = check_message_sent_simple(driver, process_id, message_to_send, automation_state)
                    
                    if is_delivered:
                        messages_sent += 1
                        automation_state.message_count = messages_sent
                        log_message(f'{process_id}: ✅ Message {messages_sent} confirmed!', automation_state, log_type='success')
                    
                    # Random delay between messages
                    random_delay = random.randint(max(3, delay-2), delay+3)
                    log_message(f'{process_id}: Waiting {random_delay}s...', automation_state)
                    
                    # Countdown display for better UX
                    for i in range(random_delay, 0, -1):
                        if not automation_state.running:
                            break
                        time.sleep(1)
                    
                    if messages_sent % 3 == 0:
                        log_message(f'{process_id}: Simulating human activity...', automation_state)
                        simulate_human_activity(driver, process_id, automation_state)
                        
                else:
                    log_message(f'{process_id}: ❌ Send failed, retrying in 5s...', automation_state, log_type='error')
                    time.sleep(5)
            
            except (WebDriverException, ConnectionError) as loop_e:
                log_message(f'{process_id}: Browser/Network failure: {type(loop_e).__name__}', automation_state, log_type='critical')
                automation_state.running = False
                break 
            except Exception as loop_e:
                log_message(f'{process_id}: Loop error: {type(loop_e).__name__}', automation_state, log_type='critical')
                time.sleep(5)
                continue

        log_message(f'{process_id}: 🎉 Loop stopped. {messages_sent} messages sent', automation_state, log_type='success')
        return messages_sent
        
    except Exception as main_e:
        log_message(f'{process_id}: 🚨 FATAL CRASH: {type(main_e).__name__}', automation_state, log_type='critical')
        return messages_sent
        
    finally:
        automation_state.running = False
        automation_state.immediate_logs_started = False
        set_automation_running(user_id, False) 
        if driver:
            try:
                log_message(f'{process_id}: Closing browser...', automation_state)
                driver.quit()
                log_message(f'{process_id}: Browser closed', automation_state, log_type='success')
            except:
                log_message(f'{process_id}: Browser close failed but process stopped.', automation_state, log_type='error')

# --- FIXED STREAMLIT CONTROL FUNCTIONS ---

def run_automation_with_notification(user_config, username, automation_state, user_id):
    """Run automation with proper error handling"""
    try:
        send_messages(user_config, automation_state, user_id) 
    except Exception as e:
        log_message(f'Automation thread crashed: {str(e)}', automation_state, log_type='critical')
    finally:
        automation_state.running = False
        automation_state.immediate_logs_started = False
        set_automation_running(user_id, False)
        log_message('Automation thread stopped completely', automation_state, log_type='success')

def start_automation(user_config, user_id):
    """Start automation with thread safety"""
    automation_state = st.session_state.automation_state
    
    # Thread safety check
    with automation_state.thread_lock:
        if automation_state.running:
            log_message('Automation already running!', automation_state, log_type='error')
            return
        
        automation_state.running = True
        automation_state.message_count = 0
        automation_state.logs = [] 
        automation_state.message_rotation_index = 0
        automation_state.last_log_time = time.time() 
        automation_state.immediate_logs_started = False
        
        set_automation_running(user_id, True) 
    
    username = get_username(user_id)
    
    try:
        thread = threading.Thread(
            target=run_automation_with_notification, 
            args=(user_config, username, automation_state, user_id),
            daemon=True,
            name=f"automation_thread_{user_id}"
        )
        thread.start()
        log_message('Automation thread started successfully', automation_state, log_type='success')
    except Exception as e:
        log_message(f'Failed to start automation thread: {str(e)}', automation_state, log_type='critical')
        automation_state.running = False
        automation_state.immediate_logs_started = False
        set_automation_running(user_id, False)

def stop_automation(user_id):
    """Stop automation with proper cleanup"""
    automation_state = st.session_state.automation_state
    automation_state.running = False
    automation_state.immediate_logs_started = False
    set_automation_running(user_id, False)
    log_message('Automation stop command sent', automation_state, log_type='success')

# ✅ FIX 1: OPTIMIZED INSTANT SAVE FUNCTION
def update_config_session_state():
    """Real-time session state update"""
    if 'chat_id_input' in st.session_state:
        st.session_state.config_chat_id = st.session_state.chat_id_input
    if 'name_prefix_input' in st.session_state:
        st.session_state.config_name_prefix = st.session_state.name_prefix_input  
    if 'delay_input' in st.session_state:
        st.session_state.config_delay = st.session_state.delay_input
    if 'messages_input' in st.session_state:
        st.session_state.config_messages = st.session_state.messages_input
    if 'cookies_input' in st.session_state:
        st.session_state.config_cookies = st.session_state.cookies_input
    if 'message_source_radio' in st.session_state:
        st.session_state.config_message_source = st.session_state.message_source_radio

# ✅ FIX 2: ULTRA FAST INSTANT SAVE FUNCTION
def instant_save_configuration():
    """Ultra fast save without any delays"""
    # Immediate session state update
    update_config_session_state()
    
    # Direct database save - no processing delays
    success = update_user_config(
        st.session_state.user_id,
        st.session_state.config_chat_id,
        st.session_state.config_name_prefix,
        st.session_state.config_delay,
        st.session_state.config_cookies,
        st.session_state.config_messages,
        st.session_state.config_message_source
    )
    
    # Instant feedback
    if success:
        st.session_state.config_saved = True
        st.session_state.last_action_status = "⚡ Configuration saved INSTANTLY!"
        st.session_state.last_action_type = "success"
        st.session_state.save_clicked = True
        st.session_state.last_save_time = time.time()
    else:
        st.session_state.last_action_status = "❌ Save failed!"
        st.session_state.last_action_type = "error"
    
    # Force immediate UI update
    st.rerun()

# --- COMPLETELY FIXED MAIN STREAMLIT APP ---

def main():
    st.markdown("""
    <div class="main-header">
        <div class="profile-section">
            <img src="https://i.ibb.co/TxJ676C1/1607a26d3d01fcc1e27238d27f6c5e50.jpg" 
                 alt="MR SHARABI DP" 
                 class="profile-pic">
            <div class="profile-name">MR SHARABI</div>
        </div>
        <h1>END TO END FACEBOOK CONVO</h1>
        <p>Ultimate Messaging Automation Tool</p>
    </div>
    """, unsafe_allow_html=True)

    log_placeholder = st.empty()

    if not st.session_state.logged_in:
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Sign Up"])
        
        with tab1:
            st.markdown('<div class="main-content-box">', unsafe_allow_html=True) 
            st.markdown("### Welcome Back!")
            username = st.text_input("Username", key="login_username", placeholder="Enter your username")
            password = st.text_input("Password", key="login_password", type="password", placeholder="Enter your password")
            
            if st.button("Login", key="login_btn", use_container_width=True):
                if username and password:
                    user_id = verify_user(username, password)
                    if user_id:
                        st.session_state.logged_in = True
                        st.session_state.user_id = user_id
                        st.session_state.username = username
                        
                        user_config_initial = get_user_config(user_id)
                        if user_config_initial:
                            st.session_state.config_chat_id = user_config_initial['chat_id']
                            st.session_state.config_name_prefix = user_config_initial['name_prefix']
                            st.session_state.config_delay = user_config_initial['delay']
                            st.session_state.config_cookies = user_config_initial['cookies']
                            st.session_state.config_messages = user_config_initial['messages']
                            st.session_state.config_message_source = user_config_initial['message_source']
                            st.session_state.config_initialized = True
                        
                        should_auto_start = get_automation_running(user_id)
                        if should_auto_start and not st.session_state.automation_state.running:
                            user_config = get_user_config(user_id)
                            if user_config and user_config['chat_id']:
                                start_automation(user_config, user_id)
                        
                        st.session_state.last_action_status = f"Welcome back, {username}!"
                        st.session_state.last_action_type = "success"
                        st.rerun()
                    else:
                        st.error("Invalid username or password!")
                else:
                    st.warning("Please enter both username and password")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with tab2:
            st.markdown('<div class="main-content-box">', unsafe_allow_html=True)
            st.markdown("### Create New Account")
            new_username = st.text_input("Choose Username", key="signup_username", placeholder="Choose a unique username")
            new_password = st.text_input("Choose Password", key="signup_password", type="password", placeholder="Create a strong password")
            confirm_password = st.text_input("Confirm Password", key="confirm_password", type="password", placeholder="Re-enter your password")
            
            if st.button("Create Account", key="signup_btn", use_container_width=True):
                if new_username and new_password and confirm_password:
                    if new_password == confirm_password:
                        success, message = create_user(new_username, new_password)
                        if success:
                            st.session_state.last_action_status = f"{message} Please login now!"
                            st.session_state.last_action_type = "success"
                            st.rerun()
                        else:
                            st.error(f"{message}")
                    else:
                        st.error("Passwords do not match!")
                else:
                    st.warning("Please fill all fields")
            st.markdown('</div>', unsafe_allow_html=True)
        
        status_placeholder = st.empty()
        if 'last_action_status' in st.session_state and st.session_state.last_action_status:
            if st.session_state.last_action_type == "success":
                status_placeholder.success(st.session_state.last_action_status)
            elif st.session_state.last_action_type == "error":
                status_placeholder.error(st.session_state.last_action_status)
            
            st.session_state.last_action_status = None
            st.session_state.last_action_type = None

    else:
        if not st.session_state.auto_start_checked and st.session_state.user_id:
            st.session_state.auto_start_checked = True
            should_auto_start = get_automation_running(st.session_state.user_id)
            if should_auto_start and not st.session_state.automation_state.running:
                user_config = get_user_config(st.session_state.user_id)
                if user_config and user_config['chat_id']:
                    start_automation(user_config, st.session_state.user_id)
                    
        st.sidebar.markdown(f"### 👤 {st.session_state.username}")
        st.sidebar.markdown(f"**User ID:** {st.session_state.user_id}")
        
        if st.sidebar.button("🚪 Logout", use_container_width=True, key="logout_btn"):
            if st.session_state.automation_state.running:
                stop_automation(st.session_state.user_id)
            
            for key in list(st.session_state.keys()):
                if not key.startswith('automation_state'):
                    del st.session_state[key]
            
            st.session_state.logged_in = False
            st.rerun()
        
        user_config_db = get_user_config(st.session_state.user_id)

        if user_config_db:
            tab1, tab2 = st.tabs(["⚙️ Configuration", "🤖 Automation"])
            
            with tab1:
                st.markdown("### Your Configuration")
                
                with st.container():
                    st.markdown('<div class="config-box">', unsafe_allow_html=True)
                    
                    st.text_input("Chat/Conversation ID", 
                                  value=st.session_state.config_chat_id, 
                                  placeholder="e.g., 1362400298935018",
                                  help="Facebook conversation ID from the URL",
                                  key="chat_id_input",
                                  on_change=update_config_session_state)
                    
                    st.text_input("Name Prefix", 
                                  value=st.session_state.config_name_prefix,
                                  placeholder="e.g., [MR SHARABI]",
                                  help="Prefix to add before each message",
                                  key="name_prefix_input",
                                  on_change=update_config_session_state)
                    
                    st.number_input("Delay (seconds)", min_value=5, max_value=300, 
                                    value=st.session_state.config_delay,
                                    help="Base wait time between messages.",
                                    key="delay_input",
                                    on_change=update_config_session_state)
                    
                    st.text_area("Facebook Cookies", 
                                 value=st.session_state.config_cookies,
                                 placeholder="Paste your Facebook cookies here",
                                 height=100,
                                 help="Get this from the ladke ka bot for best results.",
                                 key="cookies_input",
                                 on_change=update_config_session_state)
                    
                    st.markdown("---")
                    st.markdown("### 📁 Message Source Selection")
                    
                    source_options = ['Direct Text Area', 'SHARABI HINDI NP', 'SHARABI ENGLISH NP']
                    default_index = source_options.index(st.session_state.config_message_source) if st.session_state.config_message_source in source_options else 0
                    
                    st.markdown('<div style="text-align: center;">', unsafe_allow_html=True)
                    message_source = st.radio("**Choose your message source:**", 
                                              options=source_options,
                                              index=default_index,
                                              key="message_source_radio",
                                              horizontal=True,
                                              on_change=update_config_session_state)
                    st.markdown('</div>', unsafe_allow_html=True)

                    if message_source == 'Direct Text Area':
                        st.text_area("✍️ Your Custom Messages (one per line)", 
                                     value=st.session_state.config_messages,
                                     placeholder="Hello!\nHow are you?\nThis is automated message",
                                     height=120,
                                     help="Each line will be sent as a separate message in rotation.",
                                     key="messages_input",
                                     on_change=update_config_session_state)
                        
                    else:
                        if message_source == 'SHARABI HINDI NP':
                            file_info = f"**{GITHUB_HINDI_FILE}**"
                            repo_link = f"https://github.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/blob/{GITHUB_BRANCH}/{GITHUB_HINDI_FILE}"
                            language = "Hindi"
                        else:
                            file_info = f"**{GITHUB_ENGLISH_FILE}**"
                            repo_link = f"https://github.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/blob/{GITHUB_BRANCH}/{GITHUB_ENGLISH_FILE}"
                            language = "English"
                        
                        st.success(f"✅ **{message_source} Activated!**")
                        
                        st.markdown(f'''
                        <div class="np-info-box">
                            <strong>📁 File:</strong> {file_info}<br>
                            <strong>🌐 Language:</strong> {language}<br>
                            <strong>🔗 Repository:</strong> <a href="{repo_link}" target="_blank">View on GitHub</a>
                        </div>
                        ''', unsafe_allow_html=True)
                        
                        if st.button("🧪 Test Connection & Preview", key="test_github_btn", use_container_width=True):
                            test_file = GITHUB_HINDI_FILE if 'HINDI' in message_source else GITHUB_ENGLISH_FILE
                            with st.spinner(f'Fetching messages from {test_file}...'):
                                test_messages = fetch_messages_from_github(test_file)
                                
                            if test_messages:
                                st.success(f"✅ Connection successful! Found **{len(test_messages)}** messages.")
                                
                                st.markdown("**📋 First 5 Messages Preview:**")
                                preview_text = ""
                                for i, msg in enumerate(test_messages[:5]):
                                    preview_text += f"{i+1}. {msg}\n"
                                
                                st.text_area("", value=preview_text.strip(), height=100, disabled=True, key="preview_area")
                                
                                st.session_state.github_test_result = "success"
                                st.session_state.github_test_messages = test_messages
                            else:
                                st.error("❌ Connection failed! Check file path or network.")
                                st.session_state.github_test_result = "error"

                    # ✅ FIX 3: OPTIMIZED INSTANT SAVE BUTTON
                    st.markdown("---")
                    col_save1, col_save2 = st.columns([3, 1])
                    
                    with col_save1:
                        # Show save status with auto-hide
                        if st.session_state.save_clicked and st.session_state.config_saved:
                            current_time = time.time()
                            if current_time - st.session_state.last_save_time < 3:  # Show for 3 seconds
                                st.markdown('<div class="save-status">', unsafe_allow_html=True)
                                st.success("✅ Configuration saved INSTANTLY!")
                                st.markdown('</div>', unsafe_allow_html=True)
                    
                    with col_save2:
                        st.markdown('<div class="instant-save-btn">', unsafe_allow_html=True)
                        if st.button("💾 INSTANT SAVE", 
                                   use_container_width=True, 
                                   key="instant_save_btn",
                                   type="primary",
                                   help="Click to save configuration instantly without delays"):
                            instant_save_configuration()
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    st.markdown('</div>', unsafe_allow_html=True)
            
            with tab2:
                st.markdown("### Automation Control")
                
                with st.container():
                    st.markdown('<div class="automation-box">', unsafe_allow_html=True)
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("📨 Verified Messages", st.session_state.automation_state.message_count)
                    
                    with col2:
                        status_class = "status-running" if st.session_state.automation_state.running else "status-stopped"
                        status_text = "🟢 RUNNING" if st.session_state.automation_state.running else "🔴 STOPPED"
                        status_icon = "▶️" if st.session_state.automation_state.running else "⏹️"
                        st.markdown(f'**📊 STATUS**<div class="{status_class}">{status_icon} {status_text}</div>', unsafe_allow_html=True)
                    
                    with col3:
                        st.metric("📋 Total Logs", len(st.session_state.automation_state.logs))
                    
                    col1, col2 = st.columns(2)
                    
                    st.markdown('<div class="sharabi-btn">', unsafe_allow_html=True) 
                    
                    with col1:
                        start_disabled = st.session_state.automation_state.running or not user_config_db['chat_id']
                        if st.button("🚀 SHARABI END TO END START", 
                                   disabled=start_disabled, 
                                   use_container_width=True, 
                                   key="start_auto_btn"):
                            current_config = get_user_config(st.session_state.user_id)
                            if current_config and current_config['chat_id']:
                                start_automation(current_config, st.session_state.user_id)
                                st.session_state.last_action_status = "🚀 Automation started successfully!"
                                st.session_state.last_action_type = "success"
                                st.rerun()
                            else:
                                st.error("❌ Please configure Chat ID first!")
                    
                    with col2:
                        stop_disabled = not st.session_state.automation_state.running
                        if st.button("🛑 SHARABI END TO END STOP", 
                                   disabled=stop_disabled, 
                                   use_container_width=True, 
                                   key="stop_auto_btn"):
                            stop_automation(st.session_state.user_id)
                            st.session_state.last_action_status = "🛑 Automation stopped successfully!"
                            st.session_state.last_action_type = "success"
                            st.rerun()

                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    st.markdown("---")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.info(f"**Current Message Source:** {st.session_state.config_message_source}")
                    
                    with col2:
                        db_status = get_automation_running(st.session_state.user_id)
                        sync_status = "✅ SYNCED" if db_status == st.session_state.automation_state.running else "⚠️ OUT OF SYNC"
                        st.info(f"**Database Sync:** {sync_status}")
                    
                    status_placeholder = st.empty()
                    if 'last_action_status' in st.session_state and st.session_state.last_action_status:
                        if st.session_state.last_action_type == "success":
                            status_placeholder.success(st.session_state.last_action_status)
                        elif st.session_state.last_action_type == "error":
                            status_placeholder.error(st.session_state.last_action_status)
                        
                        st.session_state.last_action_status = None
                        st.session_state.last_action_type = None

                    st.markdown('</div>', unsafe_allow_html=True)
                
                st.markdown("### 📜 Live Logs")
                
                if st.session_state.automation_state.logs:
                    logs_html = '<div class="log-container" id="log-scroll-container">'
                    logs_to_display = st.session_state.automation_state.logs[-200:]
                    for log in logs_to_display: 
                        logs_html += f'<div>{log}</div>'
                    logs_html += '</div>'
                    
                    log_placeholder.markdown(logs_html, unsafe_allow_html=True)
                    
                    scroll_script = """
                    <script>
                        setTimeout(function() {
                            const logContainer = window.parent.document.querySelector('#log-scroll-container');
                            if (logContainer) {
                                logContainer.scrollTop = logContainer.scrollHeight;
                            }
                        }, 100);
                    </script>
                    """
                    st.markdown(scroll_script, unsafe_allow_html=True)
                else:
                    log_placeholder.info("No logs yet. Start automation to see logs here.")
                
                # ✅ FIX 4: OPTIMIZED AUTO-REFRESH FOR IMMEDIATE LOGS
                if st.session_state.automation_state.running:
                    current_time = time.time()
                    
                    new_log_arrived = (len(st.session_state.automation_state.logs) != st.session_state.last_log_count)
                    time_for_force_refresh = (current_time - st.session_state.automation_state.last_log_time >= 2.0)
                    
                    if new_log_arrived or time_for_force_refresh:
                        st.session_state.last_log_count = len(st.session_state.automation_state.logs)
                        st.session_state.automation_state.last_log_time = current_time
                        st.rerun()

    st.markdown('<div class="footer">Tool made by MR SHARABI | WhatsApp: 9024870456 | 2025 All Rights Reserved</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
