<?php

namespace App\Services;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;

class AttachmentService
{
    /**
     * Max allowed file size in bytes (10MB).
     */
    public const MAX_FILE_SIZE = 10 * 1024 * 1024;

    /**
     * Max pixel dimension for optimized images.
     */
    public const MAX_IMAGE_DIMENSION = 1280;

    /**
     * JPEG compression quality (0-100).
     */
    public const JPEG_QUALITY = 80;

    /**
     * Optimize and store an image/file into private ticket storage.
     *
     * @param string|resource|\Illuminate\Http\UploadedFile $source Binary data, file path, or UploadedFile
     * @param int|string $ticketId
     * @param string|null $originalName
     * @return array Metadata to store in database attachments column
     */
    public static function optimizeAndSave(mixed $source, int|string $ticketId, ?string $originalName = null): ?array
    {
        try {
            $binary = '';
            $mimeType = 'application/octet-stream';
            $size = 0;

            if ($source instanceof \Illuminate\Http\UploadedFile) {
                $binary = file_get_contents($source->getRealPath());
                $originalName = $originalName ?: $source->getClientOriginalName();
                $mimeType = $source->getMimeType() ?: 'image/jpeg';
                $size = $source->getSize();
            } elseif (is_string($source)) {
                if (file_exists($source)) {
                    $binary = file_get_contents($source);
                    $size = filesize($source);
                } else {
                    $binary = $source;
                    $size = strlen($source);
                }
                $originalName = $originalName ?: 'attachment_' . time() . '.jpg';
            }

            if (empty($binary) || $size > self::MAX_FILE_SIZE) {
                Log::warning("AttachmentService: File rejected. Size {$size} bytes exceeds limit or empty.");
                return null;
            }

            $uuid = (string) Str::uuid();
            $dir = "private/tickets/{$ticketId}";
            
            // Try optimizing image using GD if binary is an image
            $optimizedBinary = self::compressImageBinary($binary, $mimeType);

            if ($optimizedBinary !== null) {
                $fileName = "{$uuid}.jpg";
                $filePath = "{$dir}/{$fileName}";
                Storage::disk('local')->put($filePath, $optimizedBinary);
                $finalSize = strlen($optimizedBinary);
                $mimeType = 'image/jpeg';
            } else {
                // Non-image document or PDF
                $ext = pathinfo($originalName, PATHINFO_EXTENSION) ?: 'bin';
                $fileName = "{$uuid}.{$ext}";
                $filePath = "{$dir}/{$fileName}";
                Storage::disk('local')->put($filePath, $binary);
                $finalSize = strlen($binary);
            }

            return [
                'id' => $uuid,
                'name' => $originalName ?: $fileName,
                'file_name' => $fileName,
                'file_path' => $filePath,
                'mime_type' => $mimeType,
                'size' => $finalSize,
                'url' => "/api/tickets/{$ticketId}/attachments/{$fileName}",
            ];
        } catch (\Exception $e) {
            Log::error("AttachmentService optimizeAndSave error: " . $e->getMessage());
            return null;
        }
    }

    /**
     * Download a photo from Telegram, optimize it, and save to ticket storage.
     */
    public static function downloadTelegramPhoto(string $botToken, string $fileId, int|string $ticketId, ?string $caption = null): ?array
    {
        try {
            // 1. Get Telegram file path
            $res = Http::timeout(10)->get("https://api.telegram.org/bot{$botToken}/getFile", [
                'file_id' => $fileId,
            ]);

            if (!$res->successful() || !$res->json('ok')) {
                Log::error("Failed to get Telegram file info for file_id {$fileId}: " . $res->body());
                return null;
            }

            $filePath = $res->json('result.file_path');
            if (empty($filePath)) {
                return null;
            }

            // 2. Download file binary from Telegram CDN
            $downloadUrl = "https://api.telegram.org/file/bot{$botToken}/{$filePath}";
            $downloadRes = Http::timeout(20)->get($downloadUrl);

            if (!$downloadRes->successful()) {
                Log::error("Failed to download Telegram file from {$downloadUrl}");
                return null;
            }

            $originalName = basename($filePath);
            return self::optimizeAndSave($downloadRes->body(), $ticketId, $originalName);
        } catch (\Exception $e) {
            Log::error("AttachmentService downloadTelegramPhoto error: " . $e->getMessage());
            return null;
        }
    }

    /**
     * Send photo to citizen on Telegram from local storage.
     */
    public static function sendPhotoToTelegram(string $botToken, int|string $chatId, string $localFilePath, ?string $caption = null): bool
    {
        try {
            if (!Storage::disk('local')->exists($localFilePath)) {
                Log::error("Local attachment not found at {$localFilePath}");
                return false;
            }

            $binary = Storage::disk('local')->get($localFilePath);
            $fileName = basename($localFilePath);

            $req = Http::timeout(20)
                ->attach('photo', $binary, $fileName);

            $params = ['chat_id' => $chatId];
            if (!empty($caption)) {
                $params['caption'] = $caption;
            }

            $res = $req->post("https://api.telegram.org/bot{$botToken}/sendPhoto", $params);

            return $res->successful() && $res->json('ok');
        } catch (\Exception $e) {
            Log::error("AttachmentService sendPhotoToTelegram error: " . $e->getMessage());
            return false;
        }
    }

    /**
     * Compress and downscale image binary to maximum 1280px JPG (quality 80%).
     */
    protected static function compressImageBinary(string $binary, string &$mimeType): ?string
    {
        if (!function_exists('imagecreatefromstring')) {
            return null;
        }

        $srcImg = @imagecreatefromstring($binary);
        if (!$srcImg) {
            return null;
        }

        $origWidth = imagesx($srcImg);
        $origHeight = imagesy($srcImg);

        if ($origWidth <= 0 || $origHeight <= 0) {
            imagedestroy($srcImg);
            return null;
        }

        // Calculate proportional scale
        $targetWidth = $origWidth;
        $targetHeight = $origHeight;
        $maxDim = self::MAX_IMAGE_DIMENSION;

        if ($origWidth > $maxDim || $origHeight > $maxDim) {
            if ($origWidth >= $origHeight) {
                $targetWidth = $maxDim;
                $targetHeight = (int) round(($origHeight / $origWidth) * $maxDim);
            } else {
                $targetHeight = $maxDim;
                $targetWidth = (int) round(($origWidth / $origHeight) * $maxDim);
            }
        }

        // Create resized true-color canvas
        $dstImg = imagecreatetruecolor($targetWidth, $targetHeight);

        // Fill white background for transparent PNG/GIF
        $white = imagecolorallocate($dstImg, 255, 255, 255);
        imagefilledrectangle($dstImg, 0, 0, $targetWidth, $targetHeight, $white);

        imagecopyresampled($dstImg, $srcImg, 0, 0, 0, 0, $targetWidth, $targetHeight, $origWidth, $origHeight);

        // Output JPEG buffer
        ob_start();
        imagejpeg($dstImg, null, self::JPEG_QUALITY);
        $compressed = ob_get_clean();

        imagedestroy($srcImg);
        imagedestroy($dstImg);

        $mimeType = 'image/jpeg';
        return $compressed ?: null;
    }
}
