#!/usr/bin/env bash
# ==============================================================================
# Script Menghentikan Seluruh Layanan Agentic AI & Admin Panel
# ==============================================================================

echo "Menghentikan seluruh service aplikasi..."
pkill -f "uvicorn app.main:app" || true
pkill -f "celery -A app.tasks" || true
pkill -f "artisan serve" || true
pkill -f "vite" || true
echo "Semua service (FastAPI, Celery, Laravel, Vite) telah dihentikan."
