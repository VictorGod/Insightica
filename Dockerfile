FROM python:3.10-slim-buster
WORKDIR /usr/src/app

# 1) Устанавливаем системные зависимости, shadowsocks-libev и совместимый Chromium/Driver
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

# 2) Делаем бинарь ss-local явно исполняемым и убеждаемся, что работаем от root
RUN chmod +x /usr/bin/ss-local
USER root

# 3) Копируем проект
COPY . /usr/src/app/

# 4) Устанавливаем Python-зависимости
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# 5) Запускаем main.py
CMD ["python", "main.py"]
