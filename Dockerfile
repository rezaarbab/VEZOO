FROM python:3.11-slim

WORKDIR /app

# نصب dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# نصب Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نصب Playwright و Chromium
RUN playwright install chromium
RUN playwright install-deps chromium

# کپی کد
COPY bot.py .

CMD ["python", "bot.py"]
