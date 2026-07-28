FROM python:3.11-slim

WORKDIR /app

# نصب dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    lsb-release \
    && rm -rf /var/lib/apt/lists/*

# نصب Cloudflare Warp
RUN curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/cloudflare-client.list && \
    apt-get update && apt-get install -y cloudflare-warp && \
    rm -rf /var/lib/apt/lists/*

# نصب Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نصب Playwright و Chromium
RUN playwright install chromium
RUN playwright install-deps chromium

# کپی کد و startup script
COPY bot.py .
COPY start.sh .
RUN chmod +x start.sh

CMD ["./start.sh"]
