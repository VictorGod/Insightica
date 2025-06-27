FROM python:3.10-slim-buster

WORKDIR /usr/src/app

# системные библиотеки для Chrome
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      wget gnupg curl ca-certificates unzip fonts-liberation \
      libasound2 libatk1.0-0 libcups2 libexpat1 libfontconfig1 \
      libgbm1 libgconf-2-4 libgdk-pixbuf2.0-0 libglib2.0-0 \
      libgtk-3-0 libnspr4 libnss3 libpango-1.0-0 libstdc++6 \
      libx11-6 libxcb1 libxcomposite1 libxcursor1 libxdamage1 \
      libxext6 libxfixes3 libxi6 libxrandr2 libxrender1 libxss1 \
      libxtst6 && \
    rm -rf /var/lib/apt/lists/*

# Google Chrome
RUN wget -qO - https://dl.google.com/linux/linux_signing_key.pub \
      | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" \
      > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# монтируем tmpfs для /dev/shm
VOLUME ["/dev/shm"]

# копируем проект
COPY . /usr/src/app

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# кэш Selenium Manager
RUN mkdir -p /root/.cache/selenium && chmod 755 /root/.cache/selenium

ENV PYTHONUNBUFFERED=1 \
    DISPLAY=:99 \
    CHROME_BIN=/usr/bin/google-chrome \
    SE_CACHE_PATH=/root/.cache/selenium \
    TMPDIR=/tmp

# проверка
RUN google-chrome --version

CMD ["python", "main.py"]
