FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Blender の実行に必要な最小限の依存
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget xz-utils python3 python3-pip \
    libgles2 libgl1 libglib2.0-0 libgomp1 \
    libxi6 libxrender1 libsm6 libice6 \
    && rm -rf /var/lib/apt/lists/*

# Blender 4.1 LTS をダウンロード
RUN wget -q https://download.blender.org/release/Blender4.1/blender-4.1.1-linux-x64.tar.xz \
    && tar -xf blender-4.1.1-linux-x64.tar.xz \
    && mv blender-4.1.1-linux-x64 /opt/blender \
    && rm blender-4.1.1-linux-x64.tar.xz

WORKDIR /app

COPY backend/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
