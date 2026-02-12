FROM python:3.11-slim

# Prevent Python from writing .pyc and enable unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ---- System dependencies for Playwright Chromium ----
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Playwright Chromium runtime dependencies
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxcomposite1 libxdamage1 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0 \
    libxshmfence1 libx11-xcb1 libxcb-dri3-0 libxfixes3 \
    libgtk-3-0 libgdk-pixbuf2.0-0 \
    # Chinese fonts
    fonts-wqy-zenhei fonts-wqy-microhei \
    && rm -rf /var/lib/apt/lists/*

# ---- Python dependencies ----
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Install Playwright Chromium browser ----
RUN playwright install chromium

# ---- Application code ----
COPY app/ ./app/
COPY tests/ ./tests/

# ---- Create temp directory for rendered images ----
RUN mkdir -p /tmp/image_gen

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
