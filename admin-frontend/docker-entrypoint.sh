#!/bin/sh
set -e

# Jika node_modules belum ada di volume container, pasang otomatis
if [ ! -d "/app/node_modules/vite" ]; then
    echo "[Frontend Entrypoint] Memasang dependensi frontend..."
    npm install
fi

echo "[Frontend Entrypoint] Memulai Vite dev server pada port 5173..."
exec node ./node_modules/vite/bin/vite.js --host 0.0.0.0 --port 5173
