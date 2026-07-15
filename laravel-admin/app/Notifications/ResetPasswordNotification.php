<?php

namespace App\Notifications;

use Illuminate\Auth\Notifications\ResetPassword as BaseResetPassword;
use Illuminate\Notifications\Messages\MailMessage;

class ResetPasswordNotification extends BaseResetPassword
{
    /**
     * Build the mail representation of the notification.
     */
    public function toMail(mixed $notifiable): MailMessage
    {
        $url = $this->resetUrl($notifiable);

        return (new MailMessage)
            ->subject('Reset Password — Agentic Copilot Admin')
            ->view('emails.reset-password', [
                'url'      => $url,
                'name'     => $notifiable->name,
                'expireIn' => config('auth.passwords.'.config('auth.defaults.passwords').'.expire'),
            ]);
    }
}
