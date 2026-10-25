#!/usr/bin/env python3
"""Keep disposable real backend services and the unmodified Vite app for CLI browser checks.

Run with python-ai/venv/bin/python. Create the printed stop_file to shut down
owned services. The browser account is synthetic and exists only in this run.
"""

import argparse
import json
import signal
import subprocess
import time

import fitz
import httpx

from run_document_pipeline import AI, LARAVEL, REPO, Run, unused_port


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ollama-url', default='http://127.0.0.1:11434')
    parser.add_argument('--vision-model', default='qwen2.5vl:7b-q4_K_M')
    parser.add_argument('--chat-model', default='qwen2.5:3b')
    parser.add_argument('--timeout-seconds', type=int, default=3600)
    args = parser.parse_args()
    run = Run(args)
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrupted)
    code = 1
    try:
        run.prepare()
        port = unused_port()
        frontend = f'http://127.0.0.1:{port}'
        run.ports['frontend'] = port
        run.env.update({
            'VITE_LARAVEL_URL': run.laravel_url, 'VITE_AI_URL': run.ai_url,
            'SANCTUM_STATEFUL_DOMAINS': f'127.0.0.1:{port},127.0.0.1:{run.ports["laravel"]}',
            'CORS_ALLOW_ORIGINS': frontend,
        })
        fixture = subprocess.run(['php', 'scripts/integration/browser-fixtures.php'], cwd=LARAVEL,
                                 env=run.env, capture_output=True, text=True, timeout=60)
        (run.root / 'browser-fixtures.log').write_text(fixture.stdout + fixture.stderr)
        if fixture.returncode:
            raise RuntimeError('isolated browser fixtures failed; inspect browser-fixtures.log')
        ids = json.loads(fixture.stdout)
        native = run.root / 'browser-native.pdf'
        with fitz.open() as pdf:
            for number in (1, 2):
                page = pdf.new_page()
                text = (f'PANDUAN BROWSER SINTETIS HALAMAN {number}\n\n'
                        'Dokumen ini hanya digunakan untuk pengujian aplikasi admin. '
                        'Petugas memeriksa nomor registrasi, kelengkapan berkas, dan tanggal penerimaan. '
                        'Teks native dapat diekstrak tanpa model vision. '
                        'Korektor memeriksa hasil, menyimpan perubahan, dan berpindah halaman. '
                        'Indentasi dan newline hasil koreksi harus tersimpan utuh. '
                        'Seluruh identitas serta isi adalah data sintetis untuk pengujian lokal.')
                assert page.insert_textbox(fitz.Rect(45, 60, 550, 780), text, fontsize=15) >= 0
                assert len(page.get_text()) > 300
            pdf.save(native)
        run.start_apps()
        run.spawn('vite', ['npm', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', str(port), '--strictPort'], REPO / 'admin-frontend')
        def ready():
            try:
                return httpx.get(frontend + '/login', trust_env=False, timeout=2).status_code == 200
            except httpx.RequestError:
                return False
        run.wait_for(ready, 40, 'isolated Vite frontend did not become ready')
        metadata = {'frontend_url': frontend, 'backend_url': run.laravel_url,
                    'native_pdf': str(native), 'ticket_ids': ids['ticket_ids'],
                    'stop_file': str(run.root / 'stop-browser'), 'run_directory': str(run.root)}
        (run.root / 'browser.json').write_text(json.dumps(metadata, indent=2) + '\n')
        run.report['status'] = 'ready_for_browser'
        run.save()
        print('BROWSER_READY ' + json.dumps(metadata), flush=True)
        deadline = time.monotonic() + args.timeout_seconds
        while time.monotonic() < deadline and not (run.root / 'stop-browser').exists():
            for name, process in run.processes:
                if process.poll() is not None:
                    raise RuntimeError(f'{name} exited; inspect isolated logs')
            time.sleep(1)
        run.report['status'] = 'stopped'
        code = 0
    except (Exception, KeyboardInterrupt) as error:
        run.report['status'] = 'failed'
        run.report['error'] = {'type': type(error).__name__, 'message': str(error)}
        print(f'BROWSER_ENVIRONMENT_FAILED {type(error).__name__}: {error}', flush=True)
    finally:
        run.close()
    return code


if __name__ == '__main__':
    raise SystemExit(main())
