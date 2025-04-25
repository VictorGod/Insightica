FROM python:3.10-slim-buster

WORKDIR /usr/src/app

RUN apt-get update && \
    apt-get install -y \
    gcc \
    libffi-dev \
    libssl-dev \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    build-essential \
    && apt-get install -y python3-setuptools python3-wheel \
    && rm -rf /var/lib/apt/lists/*

COPY . /usr/src/app/
COPY .env /usr/src/app/.env

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

CMD ["python", "main.py"]
