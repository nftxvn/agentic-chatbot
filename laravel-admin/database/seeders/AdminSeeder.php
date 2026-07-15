<?php

namespace Database\Seeders;

use App\Models\User;
use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\Hash;

class AdminSeeder extends Seeder
{
    /**
     * Seed the admin user account.
     *
     * Credentials are read from environment variables so they are never
     * hardcoded and can be changed per-environment without touching code.
     *
     * Defaults (for local development only):
     *   ADMIN_EMAIL    = admin@diskominfotik.go.id
     *   ADMIN_NAME     = Admin Diskominfotik
     *   ADMIN_PASSWORD = changeme123   ← CHANGE THIS IN PRODUCTION!
     */
    public function run(): void
    {
        User::updateOrCreate(
            [
                'email' => env('ADMIN_EMAIL', 'admin@diskominfotik.go.id'),
            ],
            [
                'name'              => env('ADMIN_NAME', 'Admin Diskominfotik'),
                'password'          => Hash::make(env('ADMIN_PASSWORD', 'changeme123')),
                'email_verified_at' => now(),
            ]
        );

        $this->command->info('Admin account seeded successfully.');
        $this->command->warn('  Email   : ' . env('ADMIN_EMAIL', 'admin@diskominfotik.go.id'));
        $this->command->warn('  Password: Set via ADMIN_PASSWORD in .env');
    }
}
