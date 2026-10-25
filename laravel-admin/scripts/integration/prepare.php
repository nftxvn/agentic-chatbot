<?php

declare(strict_types=1);

/** Seed only the disposable instance started by scripts/integration/run_document_pipeline.py. */

use App\Models\ApiKey;
use App\Models\DocumentCategory;
use App\Models\User;
use Illuminate\Contracts\Console\Kernel;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\Hash;

function refuse(string $reason): never
{
    fwrite(STDERR, "Integration preparation refused: {$reason}\n");
    exit(1);
}

function environment(string $name): string
{
    $value = getenv($name);

    return $value === false ? '' : $value;
}

if (PHP_SAPI !== 'cli' || environment('AGENTIC_INTEGRATION_RUN') !== '1') {
    refuse('requires the isolated integration runner');
}

$runDirectory = realpath(environment('INTEGRATION_RUN_DIR'));
$temporaryRoot = realpath(sys_get_temp_dir());
if ($runDirectory === false || $temporaryRoot === false
    || !str_starts_with($runDirectory, $temporaryRoot.DIRECTORY_SEPARATOR)
    || !is_file($runDirectory.'/.agentic-integration-run')
    || realpath($runDirectory.'/.agentic-integration-run') !== $runDirectory.'/.agentic-integration-run') {
    refuse('missing disposable run directory or marker');
}

$storageDirectory = realpath(environment('LARAVEL_STORAGE_PATH'));
if ($storageDirectory === false || $storageDirectory !== $runDirectory.'/storage') {
    refuse('storage must belong to this disposable run');
}

foreach (['APP_CONFIG_CACHE', 'APP_ROUTES_CACHE', 'APP_SERVICES_CACHE', 'APP_PACKAGES_CACHE', 'APP_EVENTS_CACHE'] as $name) {
    $path = environment($name);
    if (realpath(dirname($path)) !== $runDirectory.'/bootstrap-cache'
        || is_link($path) || basename($path) === '.' || basename($path) === '..') {
        refuse('application cache paths must belong to this disposable run');
    }
}

$database = environment('DB_DATABASE');
$port = filter_var(environment('DB_PORT'), FILTER_VALIDATE_INT);
if (environment('DB_CONNECTION') !== 'mysql' || environment('DB_HOST') !== '127.0.0.1'
    || $port === false || $port < 1 || $port > 65535 || $port === 3306
    || preg_match('/\Aagentic_integration_[a-f0-9]{8,32}\z/', $database) !== 1
    || environment('DB_URL') !== '' || environment('DB_SOCKET') !== '') {
    refuse('database must use the disposable TCP instance');
}

$email = environment('INTEGRATION_ADMIN_EMAIL');
$password = environment('INTEGRATION_ADMIN_PASSWORD');
$apiKey = environment('INTEGRATION_API_KEY');
$visionModel = environment('INTEGRATION_VISION_MODEL');
if (filter_var($email, FILTER_VALIDATE_EMAIL) === false || !str_ends_with($email, '.test')
    || strlen($password) < 16 || strlen($apiKey) < 32 || $visionModel === '') {
    refuse('missing synthetic account, API key, or vision model');
}

require dirname(__DIR__, 2).'/vendor/autoload.php';

$phase = 'application bootstrap';
try {
    $app = require dirname(__DIR__, 2).'/bootstrap/app.php';
    $app->make(Kernel::class)->bootstrap();

    // Inspect resolved configuration too: cached settings or DB_URL must never redirect migrations.
    if (config('database.default') !== 'mysql'
        || config('database.connections.mysql.host') !== '127.0.0.1'
        || (int) config('database.connections.mysql.port') !== $port
        || config('database.connections.mysql.database') !== $database
        || !empty(config('database.connections.mysql.url'))
        || !empty(config('database.connections.mysql.unix_socket'))
        || realpath(storage_path()) !== $storageDirectory
        || config('app.env') === 'production'
        || config('mail.default') !== 'array'
        || !in_array(config('broadcasting.default'), [null, 'null'], true)
        || config('queue.default') !== 'sync'
        || config('cache.default') !== 'array'
        || config('session.driver') !== 'file') {
        refuse('resolved application configuration is not isolated');
    }

    $phase = 'migrations';
    if (Artisan::call('migrate', ['--force' => true, '--no-interaction' => true]) !== 0) {
        refuse('migrations failed; inspect the isolated application log');
    }

    $phase = 'synthetic fixtures';
    $admin = User::firstOrCreate(['email' => $email], [
        'name' => 'Integration Admin',
        'password' => Hash::make($password),
    ]);
    $category = DocumentCategory::firstOrCreate(['name' => 'Integration Synthetic Documents'], [
        'description' => 'Disposable integration fixture; contains no citizen data.',
        'vision_model' => $visionModel,
        'is_active' => true,
    ]);
    ApiKey::firstOrCreate(['key' => $apiKey], [
        'name' => 'Integration Synthetic Client',
        'is_active' => true,
        'webhook_enabled' => false,
    ]);

    echo json_encode(['admin_id' => $admin->id, 'category_id' => $category->id], JSON_THROW_ON_ERROR).PHP_EOL;
} catch (Throwable $error) {
    // Connection errors can contain database credentials. Keep terminal output deliberately bounded.
    refuse($phase.' failed ('.$error::class.'); inspect isolated application logs');
}
