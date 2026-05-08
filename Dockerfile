# syntax=docker/dockerfile:1.6
FROM python:3.12-slim

# 系統相依：
# - fonts-wqy-microhei → PDF 中文字型（TrueType，ReportLab 可讀；
#   Noto CJK 用 PostScript outlines，ReportLab 不支援，故不採用）
# - tini → 正確處理 PID 1 訊號（gunicorn 收得到 SIGTERM）
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        fonts-wqy-microhei \
        tini \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# 先裝套件，讓快取對 requirements.txt 失效時才會 reinstall
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製專案
COPY . .

# 確保 SQLite 寫入位置存在（資料持久化由 Render Disk 或 volume 掛載提供）
RUN mkdir -p /app/database

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sh", "-c", "gunicorn 'app:create_app()' --bind 0.0.0.0:${PORT} --workers 2 --timeout 60"]
