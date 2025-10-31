#!/bin/bash

# =======================================================
# Streamlit Cloud Chromium/ChromeDriver Setup Script
# Created for reliable execution on Ubuntu-based systems (Streamlit/Heroku).
# =======================================================

echo "--- 🚀 Starting Chromium/ChromeDriver Setup ---"

# 1. Update package list
echo "1. Updating package list..."
apt-get update -y

# 2. Install required packages from packages.txt (Redundant but safe)
# Note: These should ideally be listed in packages.txt, but installation here ensures they are present.
echo "2. Installing chromium and chromedriver..."
apt-get install -y chromium chromium-driver chromium-l10n

# 3. Create Symlinks for Universal Compatibility
# Streamlit/Selenium expects these common paths.

# Check if chromium is correctly linked as 'google-chrome'
if [ ! -f /usr/bin/google-chrome ]; then
    echo "3a. Creating symlink: /usr/bin/google-chrome -> /usr/bin/chromium"
    ln -sf /usr/bin/chromium /usr/bin/google-chrome
fi

# Check if chromedriver is correctly linked
if [ ! -f /usr/local/bin/chromedriver ]; then
    echo "3b. Creating symlink: /usr/local/bin/chromedriver -> /usr/bin/chromedriver"
    ln -sf /usr/bin/chromedriver /usr/local/bin/chromedriver
fi

# 4. Verification Step (Optional but Recommended)
echo "4. Verifying installation paths..."
if which chromium && which chromedriver; then
    echo "✅ Verification successful: Chromium and ChromeDriver found."
else
    echo "❌ Verification failed. Check logs."
fi

echo "--- ✅ Setup completed successfully! ---"
