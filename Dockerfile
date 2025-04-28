FROM python:3.10-slim-buster

WORKDIR /usr/src/app

# 1. Системные зависимости
RUN apt-get update && \
    apt-get install -y \
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
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 2. Устанавливаем Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" \
      > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 3. Качаем ChromeDriver совпадающей версии
#    (фиксируем конкретную версию, чтобы избежать проблем с автоматическим парсингом)
ARG CHROME_DRIVER_VERSION=135.0.7049.114
RUN wget -q -O /tmp/chromedriver.zip \
      https://storage.googleapis.com/chrome-for-testing-public/${CHROME_DRIVER_VERSION}/linux64/chromedriver-linux64.zip \
    && unzip /tmp/chromedriver.zip -d /tmp \
    && mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \
    && chmod +x /usr/local/bin/chromedriver \
    && rm -rf /tmp/chromedriver.zip /tmp/chromedriver-linux64

# 4. Копируем проект
COPY . /usr/src/app/

# 5. Устанавливаем Python-зависимости
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# 6. Переменные для headless Chrome
ENV PYTHONUNBUFFERED=1 \
    DISPLAY=:99 \
    CHROME_BIN=/usr/bin/google-chrome \
    CHROME_PATH=/usr/lib/chromium/ \
    CHROME_DRIVER_PATH=/usr/local/bin/chromedriver

# 7. Запуск бота
CMD ["python", "main.py"]
