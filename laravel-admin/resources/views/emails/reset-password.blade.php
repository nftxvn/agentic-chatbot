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
<body style="margin:0;padding:0;background-color:#0b0f19;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;font-family:'Geist',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">

<!-- ===== OUTER WRAPPER ===== -->
<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%"
       style="background-color:#0b0f19;background:linear-gradient(180deg, #0b0f19 0%, #0f172a 100%);">
    <tr>
        <td align="center" style="padding:48px 16px;">

            <!-- ===== INNER CARD (580px) ===== -->
            <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="580"
                   style="max-width:580px;width:100%;border-collapse:separate;border-spacing:0;">

                <!-- ── HEADER (Dark Modern Slate with Sky Glow) ── -->
                <tr>
                    <td align="center" bgcolor="#0f172a"
                        style="background-color:#0f172a;background:linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                               padding:38px 40px 32px 40px;
                               border-radius:20px 20px 0 0;
                               border:1px solid rgba(56, 189, 248, 0.2);
                               border-bottom:none;">

                        <!-- Logo / Icon Box -->
                        <table role="presentation" border="0" cellpadding="0" cellspacing="0">
                            <tr>
                                <td align="center" width="56" height="56" bgcolor="#1e293b"
                                    style="background-color:#1e293b;
                                           border-radius:14px;
                                           border:1px solid rgba(56, 189, 248, 0.4);
                                           width:56px;height:56px;
                                           padding:12px;
                                           box-shadow:0 0 20px rgba(14, 165, 233, 0.25);">
                                    <!-- Lock/Key Icon -->
                                    <img src="https://img.icons8.com/ios-filled/50/38bdf8/password.png"
                                         alt="Agentic Security" width="30" height="30"
                                         style="display:block;border:0;outline:none;max-width:30px;height:auto;">
                                </td>
                            </tr>
                        </table>

                        <!-- Brand Title & Tagline -->
                        <table role="presentation" border="0" cellpadding="0" cellspacing="0">
                            <tr>
                                <td align="center" style="padding-top:16px;">
                                    <p style="margin:0;font-family:'Geist',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
                                               font-size:21px;font-weight:800;color:#ffffff;
                                               letter-spacing:-0.4px;">
                                        AGENTIC <span style="color:#38bdf8;">COPILOT</span>
                                    </p>
                                    <p style="margin:4px 0 0 0;font-family:'Geist',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
                                               font-size:12px;font-weight:600;color:#94a3b8;
                                               letter-spacing:0.5px;text-transform:uppercase;">
                                        Diskominfotik Kota Banda Aceh
                                    </p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>

                <!-- ── BODY CARD (Clean Bright Card) ── -->
                <tr>
                    <td bgcolor="#ffffff"
                        style="background-color:#ffffff;
                               padding:40px 44px 36px 44px;
                               border-left:1px solid #e2e8f0;
                               border-right:1px solid #e2e8f0;">

                        <!-- Heading -->
                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                            <tr>
                                <td>
                                    <h1 style="margin:0 0 10px 0;
                                               font-family:'Geist',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
                                               font-size:22px;font-weight:700;
                                               color:#0f172a;letter-spacing:-0.3px;line-height:1.3;">
                                        Permintaan Reset Password
                                    </h1>
                                    <p style="margin:0 0 24px 0;
                                               font-family:'Geist',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
                                               font-size:14px;color:#475569;
                                               line-height:1.65;">
                                        Halo <strong style="color:#0f172a;">{{ $name }}</strong>, kami menerima permintaan untuk mengatur ulang kata sandi akun Admin Dashboard Anda di sistem <strong>Agentic Copilot</strong>.
                                    </p>
                                </td>
                            </tr>
                        </table>

                        <!-- CTA Button (Sky Theme) -->
                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                            <tr>
                                <td align="center" style="padding:10px 0 28px 0;">
                                    <!--[if mso]>
                                    <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml"
                                        xmlns:w="urn:schemas-microsoft-com:office:word"
                                        href="{{ $url }}"
                                        style="height:48px;v-text-anchor:middle;width:260px;"
                                        arcsize="24%" fillcolor="#0284c7" strokecolor="#0284c7">
                                        <w:anchorlock/>
                                        <center style="color:#ffffff;font-family:sans-serif;
                                                       font-size:14px;font-weight:bold;">
                                            Buat Password Baru &rarr;
                                        </center>
                                    </v:roundrect>
                                    <![endif]-->
                                    <!--[if !mso]><!-->
                                    <a href="{{ $url }}"
                                       style="display:inline-block;padding:14px 34px;
                                              font-family:'Geist',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
                                              font-size:14px;font-weight:700;
                                              color:#ffffff;text-decoration:none;
                                              background-color:#0284c7;background:linear-gradient(135deg, #0284c7 0%, #0ea5e9 100%);
                                              border-radius:12px;
                                              box-shadow:0 4px 12px rgba(2, 132, 199, 0.35);
                                              letter-spacing:0.2px;">
                                        Buat Password Baru &rarr;
                                    </a>
                                    <!--<![endif]-->
                                </td>
                            </tr>
                        </table>

                        <!-- Security Notice Box (Sky Tint) -->
                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                            <tr>
                                <td bgcolor="#f0f9ff"
                                    style="background-color:#f0f9ff;
                                           border:1px solid #bae6fd;
                                           border-radius:12px;
                                           padding:16px 20px;">
                                    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                                        <tr>
                                            <td width="24" valign="top" style="padding-top:2px;">
                                                <span style="font-size:16px;">⏱️</span>
                                            </td>
                                            <td style="padding-left:10px;">
                                                <p style="margin:0;font-size:13px;color:#0369a1;line-height:1.5;font-weight:500;">
                                                    Tautan ini hanya berlaku selama <strong>{{ $expireIn }} menit</strong>.
                                                </p>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td width="24" valign="top" style="padding-top:10px;">
                                                <span style="font-size:16px;">🔒</span>
                                            </td>
                                            <td style="padding-left:10px;padding-top:8px;">
                                                <p style="margin:0;font-size:13px;color:#0369a1;line-height:1.5;">
                                                    Jika Anda tidak merasa melakukan permintaan ini, Anda dapat mengabaikan email ini dengan aman. Kata sandi Anda tidak akan berubah.
                                                </p>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                        </table>

                        <!-- Fallback URL Box -->
                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-top:24px;">
                            <tr>
                                <td bgcolor="#f8fafc"
                                    style="background-color:#f8fafc;
                                           border:1px solid #e2e8f0;
                                           border-radius:12px;
                                           padding:14px 18px;">
                                    <p style="margin:0 0 6px 0;
                                               font-size:11px;font-weight:700;
                                               color:#64748b;text-transform:uppercase;
                                               letter-spacing:0.5px;">
                                        Tombol tidak dapat diklik?
                                    </p>
                                    <p style="margin:0 0 6px 0;font-size:12px;color:#64748b;line-height:1.5;">
                                        Salin dan tempel tautan berikut ke peramban web Anda:
                                    </p>
                                    <p style="margin:0;font-family:'JetBrains Mono',Consolas,monospace;
                                               font-size:11px;color:#0284c7;line-height:1.5;
                                               word-break:break-all;overflow-wrap:anywhere;">
                                        {{ $url }}
                                    </p>
                                </td>
                            </tr>
                        </table>

                    </td>
                </tr>

                <!-- ── FOOTER ── -->
                <tr>
                    <td align="center" bgcolor="#f8fafc"
                        style="background-color:#f8fafc;
                               border:1px solid #e2e8f0;
                               border-top:none;
                               border-radius:0 0 20px 20px;
                               padding:24px 40px;">
                        <p style="margin:0 0 4px 0;
                                   font-size:12px;color:#64748b;line-height:1.5;">
                            Email otomatis dari sistem <strong>Agentic Copilot</strong> &middot; Layanan Dokumen Cerdas RAG
                        </p>
                        <p style="margin:0;font-size:11px;color:#94a3b8;">
                            &copy; {{ date('Y') }} Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh.
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

