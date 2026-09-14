#!/usr/bin/env bash
# ==============================================================================
# Script Peluncur Seluruh Layanan Agentic AI & Admin Panel
# ==============================================================================

set -e
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== [1/6] Memeriksa Layanan Inti (MySQL, Redis, Ollama) ==="
systemctl --no-block start mysql redis-server ollama 2>/dev/null || true
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    export OLLAMA_MODELS=/usr/share/ollama/.ollama/models
    export OLLAMA_FLASH_ATTENTION=1
    export OLLAMA_KV_CACHE_TYPE=q8_0
    nohup ollama serve > /tmp/ollama.log 2>&1 &
    sleep 2
fi

echo "=== [2/6] Menghentikan proses lama jika ada ==="
pkill -f "uvicorn app.main:app" || true
pkill -f "celery -A app.tasks" || true
pkill -f "artisan serve" || true
pkill -f "vite" || true
sleep 1

echo "=== [3/6] Menyetel ulang status ekstraksi yang tertahan ==="
cd "$ROOT_DIR/python-ai"
./venv/bin/python3 reset_jobs.py
./venv/bin/celery -A app.tasks.process_document.celery_app purge -f 2>/dev/null || true

echo "=== [4/6] Menjalankan Python AI Microservice (Port 8080) ==="
cd "$ROOT_DIR/python-ai"
nohup ./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080 > "$ROOT_DIR/python-ai/uvicorn.log" 2>&1 &

echo "=== [5/6] Menjalankan Celery Worker (GPU Extraction Queue) ==="
nohup ./venv/bin/celery -A app.tasks.process_document.celery_app worker --loglevel=info > "$ROOT_DIR/python-ai/celery.log" 2>&1 &

echo "=== [6/6] Menjalankan Laravel Backend (Port 8000) & Vite Frontend (Port 5173) ==="
cd "$ROOT_DIR/laravel-admin"
nohup php artisan serve --host 0.0.0.0 --port 8000 > "$ROOT_DIR/laravel-admin/artisan.log" 2>&1 &

cd "$ROOT_DIR/admin-frontend"
export PATH="/home/nftxvn/.nvm/versions/node/v20.20.2/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
nohup ./node_modules/vite/bin/vite.js --host 0.0.0.0 --port 5173 > "$ROOT_DIR/admin-frontend/vite.log" 2>&1 &

sleep 2
echo ""
echo "=================================================================="
echo "SEMUA LAYANAN BERHASIL DINYALAKAN!"
echo "------------------------------------------------------------------"
echo "Frontend Admin UI : http://localhost:5173"
echo "Backend Laravel   : http://localhost:8000"
echo "AI Service API    : http://localhost:8080"
echo "=================================================================="
