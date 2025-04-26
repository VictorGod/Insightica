FROM python:3.10-slim-buster

WORKDIR /usr/src/app

# Установка базовых зависимостей
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
    python3-wheel

# Установка Chrome (обновленный метод)
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Установка ChromeDriver (улучшенный метод)
RUN CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d. -f1) && \
    wget -q -O /tmp/chromedriver_linux64.zip https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/120.0.6099.109/linux64/chromedriver-linux64.zip && \
    unzip /tmp/chromedriver_linux64.zip -d /tmp && \
    mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -rf /tmp/chromedriver_linux64.zip /tmp/chromedriver-linux64

# Копируем файлы проекта
COPY . /usr/src/app/

# Устанавливаем Python зависимости
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Задаем переменные окружения для Chrome в headless режиме
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99
ENV CHROME_BIN=/usr/bin/google-chrome
ENV CHROME_PATH=/usr/lib/chromium/

# Запускаем бота
CMD ["python", "main.py"]
