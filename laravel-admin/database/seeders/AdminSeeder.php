<?php

namespace Database\Seeders;

use App\Models\User;
use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\Hash;

class AdminSeeder extends Seeder
{
    /**
     * Seed the default admin user account.
     */
    public function run(): void
    {
        User::firstOrCreate(
            [
                'email' => 'admin@diskominfotik.go.id',
            ],
            [
                'name'              => 'Admin Diskominfotik',
                'password'          => Hash::make('changeme123'),
                'email_verified_at' => now(),
            ]
        );

        $this->command->info('Admin account seeded successfully.');
        $this->command->warn('  Email   : admin@diskominfotik.go.id');
        $this->command->warn('  Password: changeme123');
    }
}
