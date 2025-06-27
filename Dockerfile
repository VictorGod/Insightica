FROM python:3.10-slim-buster

WORKDIR /usr/src/app

# Установка базовых зависимостей + системных библиотек для Chrome
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
      curl \
      ca-certificates \
      fonts-liberation \
      libasound2 \
      libatk1.0-0 \
      libcairo2 \
      libcups2 \
      libexpat1 \
      libfontconfig1 \
      libgbm1 \
      libgcc1 \
      libgconf-2-4 \
      libgdk-pixbuf2.0-0 \
      libglib2.0-0 \
      libgtk-3-0 \
      libnspr4 \
      libnss3 \
      libpango-1.0-0 \
      libstdc++6 \
      libx11-6 \
      libx11-xcb1 \
      libxcb1 \
      libxcomposite1 \
      libxcursor1 \
      libxdamage1 \
      libxext6 \
      libxfixes3 \
      libxi6 \
      libxrandr2 \
      libxrender1 \
      libxss1 \
      libxtst6 && \
    rm -rf /var/lib/apt/lists/*

# Установка Google Chrome
RUN wget -qO - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" \
      > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# Копируем файлы проекта
COPY . /usr/src/app/

# Устанавливаем Python зависимости
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Создаем директории для кэша Selenium Manager
RUN mkdir -p /root/.cache/selenium && \
    chmod 755 /root/.cache/selenium

# Задаем переменные окружения
ENV PYTHONUNBUFFERED=1 \
    DISPLAY=:99 \
    CHROME_BIN=/usr/bin/google-chrome \
    SE_AVOID_STATS=true \
    SE_CACHE_PATH=/root/.cache/selenium

# Проверяем что Chrome установлен правильно
RUN google-chrome --version

# Запускаем бота
CMD ["python", "main.py"]
