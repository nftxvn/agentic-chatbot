<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="id">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="x-apple-disable-message-reformatting">
    <title>Reset Password — Agentic Copilot Admin</title>
    <!--[if mso]>
    <noscript>
        <xml>
            <o:OfficeDocumentSettings>
                <o:PixelsPerInch>96</o:PixelsPerInch>
            </o:OfficeDocumentSettings>
        </xml>
    </noscript>
    <![endif]-->
</head>
<body style="margin:0;padding:0;background-color:#f0f2f5;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">

<!-- ===== OUTER WRAPPER ===== -->
<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%"
       style="background-color:#f0f2f5;">
    <tr>
        <td align="center" style="padding:40px 16px;">

            <!-- ===== INNER CARD (600px) ===== -->
            <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="600"
                   style="max-width:600px;width:100%;">

                <!-- ── HEADER ── -->
                <tr>
                    <td align="center" bgcolor="#4f46e5"
                        style="background-color:#4f46e5;
                               padding:36px 48px 32px 48px;
                               border-radius:16px 16px 0 0;">

                        <!-- Icon box -->
                        <table role="presentation" border="0" cellpadding="0" cellspacing="0">
                            <tr>
                                <td align="center" width="56" height="56" bgcolor="#ffffff"
                                    style="background-color:rgba(255,255,255,0.15);
                                           border-radius:14px;
                                           width:56px;height:56px;
                                           padding:14px;">
                                    <!--[if mso]><v:roundrect xmlns:v="urn:schemas-microsoft-com:vml"
                                        style="width:56px;height:56px;" arcsize="25%" fillcolor="#8080ff">
                                        <v:textbox inset="14px,14px,14px,14px"><![endif]-->
                                    <img src="https://img.icons8.com/ios-filled/50/ffffff/monitor.png"
                                         alt="Agentic" width="28" height="28"
                                         style="display:block;border:0;outline:none;
                                                max-width:28px;height:auto;">
                                    <!--[if mso]></v:textbox></v:roundrect><![endif]-->
                                </td>
                            </tr>
                        </table>

                        <!-- Brand name -->
                        <table role="presentation" border="0" cellpadding="0" cellspacing="0">
                            <tr>
                                <td align="center" style="padding-top:16px;">
                                    <p style="margin:0;font-family:Arial,Helvetica,sans-serif;
                                               font-size:20px;font-weight:bold;color:#ffffff;
                                               letter-spacing:0.3px;">
                                        Agentic Copilot
                                    </p>
                                    <p style="margin:6px 0 0 0;font-family:Arial,Helvetica,sans-serif;
                                               font-size:13px;color:#c7d2fe;">
                                        Admin Dashboard &middot; Diskominfotik
                                    </p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>

                <!-- ── BODY ── -->
                <tr>
                    <td bgcolor="#ffffff"
                        style="background-color:#ffffff;padding:44px 48px 40px 48px;">

                        <!-- Greeting -->
                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                            <tr>
                                <td>
                                    <p style="margin:0 0 8px 0;
                                               font-family:Arial,Helvetica,sans-serif;
                                               font-size:22px;font-weight:bold;
                                               color:#111827;line-height:1.3;">
                                        Halo, {{ $name }}!
                                    </p>
                                    <p style="margin:0 0 32px 0;
                                               font-family:Arial,Helvetica,sans-serif;
                                               font-size:15px;color:#6b7280;
                                               line-height:1.7;">
                                        Kami menerima permintaan untuk mereset password akun Anda
                                        di <strong style="color:#374151;">Agentic Copilot Admin Dashboard</strong>.
                                        Klik tombol di bawah untuk melanjutkan proses reset password.
                                    </p>
                                </td>
                            </tr>
                        </table>

                        <!-- CTA Button -->
                        <table role="presentation" border="0" cellpadding="0" cellspacing="0">
                            <tr>
                                <td align="center" bgcolor="#4f46e5"
                                    style="background-color:#4f46e5;border-radius:10px;
                                           mso-padding-alt:0;">
                                    <!--[if mso]>
                                    <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml"
                                        xmlns:w="urn:schemas-microsoft-com:office:word"
                                        href="{{ $url }}"
                                        style="height:52px;v-text-anchor:middle;width:240px;"
                                        arcsize="10%" fillcolor="#4f46e5" strokecolor="#4f46e5">
                                        <w:anchorlock/>
                                        <center style="color:#ffffff;font-family:Arial,Helvetica,sans-serif;
                                                       font-size:15px;font-weight:bold;">
                                            Reset Password Saya
                                        </center>
                                    </v:roundrect>
                                    <![endif]-->
                                    <!--[if !mso]><!-->
                                    <a href="{{ $url }}"
                                       style="display:inline-block;padding:15px 32px;
                                              font-family:Arial,Helvetica,sans-serif;
                                              font-size:15px;font-weight:bold;
                                              color:#ffffff;text-decoration:none;
                                              background-color:#4f46e5;border-radius:10px;
                                              mso-hide:all;">
                                        Reset Password Saya
                                    </a>
                                    <!--<![endif]-->
                                </td>
                            </tr>
                        </table>

                        <!-- Spacer -->
                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                            <tr><td style="padding-top:32px;"></td></tr>
                        </table>

                        <!-- Divider -->
                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                            <tr>
                                <td style="border-top:1px solid #e5e7eb;padding-top:28px;"></td>
                            </tr>
                        </table>

                        <!-- Notice 1: Expiry -->
                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                            <tr>
                                <td style="padding-bottom:12px;">
                                    <p style="margin:0;font-family:Arial,Helvetica,sans-serif;
                                               font-size:13px;color:#6b7280;line-height:1.7;">
                                        &#9200;&nbsp; Link ini akan kadaluarsa dalam
                                        <strong style="color:#374151;">{{ $expireIn }} menit</strong>.
                                    </p>
                                </td>
                            </tr>
                            <!-- Notice 2: Security -->
                            <tr>
                                <td style="padding-bottom:28px;">
                                    <p style="margin:0;font-family:Arial,Helvetica,sans-serif;
                                               font-size:13px;color:#6b7280;line-height:1.7;">
                                        &#128274;&nbsp; Jika Anda tidak merasa melakukan permintaan ini,
                                        abaikan email ini.
                                        Password Anda <strong style="color:#374151;">tidak akan berubah</strong>.
                                    </p>
                                </td>
                            </tr>
                        </table>

                        <!-- Fallback URL box -->
                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                            <tr>
                                <td bgcolor="#f9fafb"
                                    style="background-color:#f9fafb;border:1px solid #e5e7eb;
                                           border-radius:10px;padding:16px 20px;">
                                    <p style="margin:0 0 6px 0;
                                               font-family:Arial,Helvetica,sans-serif;
                                               font-size:11px;font-weight:bold;
                                               color:#9ca3af;text-transform:uppercase;
                                               letter-spacing:0.5px;">
                                        Tombol tidak berfungsi?
                                    </p>
                                    <p style="margin:0 0 8px 0;
                                               font-family:Arial,Helvetica,sans-serif;
                                               font-size:12px;color:#6b7280;line-height:1.6;">
                                        Salin dan tempel URL berikut ke browser Anda:
                                    </p>
                                    <p style="margin:0;font-family:Arial,Helvetica,sans-serif;
                                               font-size:12px;color:#4f46e5;line-height:1.6;
                                               overflow-wrap:anywhere;">
                                        {{ $url }}
                                    </p>
                                </td>
                            </tr>
                        </table>

                    </td>
                </tr>

                <!-- ── FOOTER ── -->
                <tr>
                    <td align="center" bgcolor="#f9fafb"
                        style="background-color:#f9fafb;
                               border:1px solid #e5e7eb;border-top:none;
                               border-radius:0 0 16px 16px;
                               padding:24px 48px;">
                        <p style="margin:0 0 6px 0;
                                   font-family:Arial,Helvetica,sans-serif;
                                   font-size:12px;color:#9ca3af;line-height:1.6;">
                            Email ini dikirim otomatis oleh sistem <strong>Agentic Copilot</strong>.
                            Jangan membalas email ini.
                        </p>
                        <p style="margin:0;font-family:Arial,Helvetica,sans-serif;
                                   font-size:12px;color:#d1d5db;">
                            &copy; {{ date('Y') }} Dinas Komunikasi dan Informatika.
                        </p>
                    </td>
                </tr>

            </table>
            <!-- /inner card -->

        </td>
    </tr>
</table>
<!-- /outer wrapper -->

</body>
</html>
