# Dikte62 — mode web (server lokal/LAN).
# Build:  docker build -t dikte62 .
# Run  :  docker run --rm -p 8777:8777 -v dikte62-data:/app/.data dikte62
# Akses:  http://localhost:8777

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface \
    XDG_CACHE_HOME=/app/.cache

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# wheel CPU agar image tidak menarik paket CUDA (~1 GB)
COPY requirements.txt ./
RUN pip install --index-url https://download.pytorch.org/whl/cpu \
      "torch==2.15.0" "torchaudio==2.11.1" \
 && pip install -r requirements.txt

COPY . .

EXPOSE 8777
VOLUME ["/app/.data"]

# Untuk akses dari luar container, tambahkan --token agar tidak terbuka bebas:
#   docker run ... dikte62 python scripts/server.py --host 0.0.0.0 --token RAHASIA
CMD ["python", "scripts/server.py", "--host", "0.0.0.0", "--port", "8777"]
