FROM python:3.10-slim-buster
WORKDIR /usr/src/app

# Устанавливаем системные зависимости, Shadowsocks-libev и Chromium/ChromeDriver
RUN apt-get update && \
    apt-get install -y \
      build-essential \
      gcc \
      libffi-dev \
      libssl-dev \
      libpq-dev \
      libjpeg-dev \
      zlib1g-dev \
      shadowsocks-libev \
      chromium=90.0.4430.212-1~deb10u1 \
      chromium-driver=90.0.4430.212-1~deb10u1 \
      libasound2 \
      libatk-bridge2.0-0 \
      libnss3 \
      xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Копируем код и скрипт запуска
COPY . /usr/src/app/
COPY start.sh /usr/src/app/start.sh

# Делаем скрипт исполняемым
RUN chmod +x /usr/src/app/start.sh

# Устанавливаем Python-зависимости
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Запускаем entrypoint
ENTRYPOINT ["/usr/src/app/start.sh"]
