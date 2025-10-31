# Stage 1: Build Stage - Install dependencies and Python environment
# We start from the official Python image
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Install System Dependencies (Chromium, ChromeDriver, etc.)
# This replaces the need for setup.sh inside Docker
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
        chromium-l10n \
        libnss3 \
        wget \
        gconf-service \
        libappindicator1 \
        libasound2 \
        libatk1.0-0 \
        libcairo2 \
        libcups2 \
        libfontconfig1 \
        libgdk-pixbuf2.0-0 \
        libgtk-3-0 \
        libjpeg-turbo8 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libxcomposite1 \
        libxcursor1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxi6 \
        libxrandr2 \
        libxrender1 \
        libxss1 \
        libxtst6 \
        ca-certificates \
        fonts-liberation \
        lsb-release \
        xdg-utils && \
    rm -rf /var/lib/apt/lists/*

# Create symlinks for universal compatibility (Same as in setup.sh)
RUN ln -sf /usr/bin/chromium /usr/bin/google-chrome && \
    ln -sf /usr/bin/chromedriver /usr/local/bin/chromedriver

# Copy requirements.txt (Assuming you have one, needed for Python libraries)
COPY requirements.txt .

# Install Python dependencies (Selenium, Streamlit)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files
COPY . .

# Expose the port Streamlit runs on (default is 8501)
EXPOSE 8501

# Command to run the Streamlit application
# We use entrypoint.sh for clean startup, but for simplicity, we use CMD directly:
CMD ["streamlit", "run", "your_main_app_file.py", "--server.port=8501", "--server.address=0.0.0.0"]
