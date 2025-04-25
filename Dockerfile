FROM python:3.10-slim-buster
WORKDIR /usr/src/app


RUN apt-get update && \
    apt-get install -y \
      build-essential gcc libffi-dev libssl-dev libpq-dev \
      libjpeg-dev zlib1g-dev shadowsocks-libev \
      chromium chromium-driver \
      libasound2 libatk-bridge2.0-0 libgtk-4-1 libnss3 xdg-utils \
    && rm -rf /var/lib/apt/lists/*


COPY . /usr/src/app/


RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt


CMD ["python", "main.py"]
