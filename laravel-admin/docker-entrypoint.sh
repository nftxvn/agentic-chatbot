#!/bin/sh
set -e

echo "[Laravel Entrypoint] Menyiapkan environment Laravel..."

# Pastikan direktori storage & bootstrap cache ada dan memiliki permission yang benar
mkdir -p /var/www/html/storage/framework/cache/data \
         /var/www/html/storage/framework/sessions \
         /var/www/html/storage/framework/views \
         /var/www/html/storage/logs \
         /var/www/html/bootstrap/cache

chmod -R 777 /var/www/html/storage /var/www/html/bootstrap/cache

# Install composer jika vendor belum ada
if [ ! -f "/var/www/html/vendor/autoload.php" ]; then
    echo "[Laravel Entrypoint] Menginstal dependensi Composer..."
    composer install --no-interaction --prefer-dist --optimize-autoloader
fi

# Generate APP_KEY jika belum ada di .env
if [ -z "" ] || [ "" = "" ]; then
    echo "[Laravel Entrypoint] Menghasilkan APP_KEY..."
    php artisan key:generate --force || true
fi

# Tunggu database MySQL siap
echo "[Laravel Entrypoint] Menunggu database MySQL terhubung..."
until php -r "try { new PDO('mysql:host=' . getenv('DB_HOST') . ';port=' . (getenv('DB_PORT') ?: '3306') . ';dbname=' . getenv('DB_DATABASE'), getenv('DB_USERNAME'), getenv('DB_PASSWORD')); exit(0); } catch (\Exception \) { exit(1); }"; do
    echo "[Laravel Entrypoint] Database MySQL belum siap, menunggu 2 detik..."
    sleep 2
done
echo "[Laravel Entrypoint] Database MySQL berhasil terhubung!"

# Jalankan migrasi database
echo "[Laravel Entrypoint] Menjalankan migrasi database..."
php artisan migrate --force || true

echo "[Laravel Entrypoint] Memulai server Laravel pada port 8000..."
exec php artisan serve --host=0.0.0.0 --port=8000
