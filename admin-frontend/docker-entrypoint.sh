#!/bin/sh
set -e

# Jika binary vite belum ada di volume container, pasang otomatis
if [ ! -f "/app/node_modules/.bin/vite" ]; then
    echo "[Frontend Entrypoint] Memasang dependensi frontend..."
    npm install
fi

echo "[Frontend Entrypoint] Memulai Vite dev server pada port 5173..."
exec npx vite --host 0.0.0.0 --port 5173
