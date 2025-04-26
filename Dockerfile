FROM python:3.10-slim-buster

WORKDIR /usr/src/app

# Установка зависимостей
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
    python3-wheel && \
    # Установка Chrome
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    # Определение версии Chrome и установка соответствующего ChromeDriver
    CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d. -f1) && \
    CHROMEDRIVER_VERSION=$(wget -qO- https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_VERSION) && \
    wget -q https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip && \
    unzip chromedriver_linux64.zip -d /usr/local/bin && \
    chmod +x /usr/local/bin/chromedriver && \
    rm chromedriver_linux64.zip && \
    # Очистка
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Копируем файлы проекта
COPY . /usr/src/app/

# Устанавливаем Python зависимости
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Задаем переменные окружения для Chrome
ENV PYTHONUNBUFFERED=1
ENV CHROME_DRIVER_PATH=/usr/local/bin/chromedriver

# Запускаем бот
CMD ["python", "main.py"]
