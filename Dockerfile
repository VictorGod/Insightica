FROM python:3.10-slim-buster

WORKDIR /usr/src/app

# 1. Системные зависимости для сборки и headless Chrome
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      gcc \
      libffi-dev \
      libssl-dev \
      libpq-dev \
      libjpeg-dev \
      zlib1g-dev \
      build-essential \
      wget \
      gnupg \
      unzip \
      python3-setuptools \
      python3-wheel \
      xvfb && \
    rm -rf /var/lib/apt/lists/*

# 2. Установка Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" \
      > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# 3. Установка ChromeDriver
RUN CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d. -f1) && \
    wget -q -O /tmp/chromedriver.zip \
      https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_VERSION}.0/linux64/chromedriver-linux64.zip && \
    unzip /tmp/chromedriver.zip -d /tmp && \
    mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -rf /tmp/chromedriver.zip /tmp/chromedriver-linux64

# 4. Копируем зависимости и устанавливаем Python-библиотеки
COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5. Копируем весь код приложения
COPY . .

# 6. Переменные для headless Chrome и Xvfb
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99
ENV CHROME_BIN=/usr/bin/google-chrome
ENV CHROME_PATH=/usr/lib/chromium/

# 7. Запуск Xvfb и бота
CMD ["sh", "-c", "Xvfb :99 -screen 0 1920x1080x24 & python main.py"]
