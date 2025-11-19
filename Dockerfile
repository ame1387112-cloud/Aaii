FROM python:3.11-slim

WORKDIR /app

# نصب dependencies سیستمی
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# نصب پکیج‌های پایتون
RUN pip install --no-cache-dir -r requirements.txt

# نصب مرورگرهای Playwright
RUN playwright install
RUN playwright install-deps

COPY . .

CMD ["python", "bot.py"]
