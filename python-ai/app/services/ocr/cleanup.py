"""Pembersihan respons vision dan pemulihan penanda daftar lintas halaman."""

import logging
import re

logger = logging.getLogger("app.services.pdf_processor")

def _strip_garbage(text: str) -> str:
    """Hapus tag HTML dan base64 image dari output LLM, tanpa merusak tabel Markdown."""
    text = re.sub(r'<img[^>]+/?>', '', text)
    
    # Bersihkan markdown code fences (misalnya ```markdown ... ```)
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split('\n')
        if len(lines) > 2 and lines[-1].strip().startswith("```"):
            text = '\n'.join(lines[1:-1])
        elif len(lines) > 1 and lines[0].strip().startswith("```"):
            text = '\n'.join(lines[1:])
    
    return text.strip()


_POLA_PENANDA_HURUF = re.compile(
    r"(?m)^(\s*)([A-Za-z]{1,2})\.(\s+)"
)


_MIN_RUNTUN_UNTUK_PERBAIKAN = 3


def perbaiki_penanda_daftar(pages_content: list[dict]) -> int:
    """
    Memulihkan penanda daftar bertingkat yang dipotong model vision.
    """
    keadaan = {
        "terakhir": None,
        "panjang_runtun": 0,
        "diperbaiki": 0,
    }

    def tangani(m: re.Match) -> str:
        spasi_awal, penanda, spasi_akhir = m.group(1), m.group(2), m.group(3)
        rendah = penanda.lower()
        terakhir = keadaan["terakhir"]

        if terakhir is None:
            keadaan["terakhir"] = rendah
            keadaan["panjang_runtun"] = 1
            return m.group(0)

        panjang = len(terakhir)
        huruf_terakhir = terakhir[0]
        huruf_berikutnya = chr(ord(huruf_terakhir) + 1)
        diharapkan = huruf_berikutnya * panjang

        if rendah == diharapkan:
            keadaan["terakhir"] = rendah
            keadaan["panjang_runtun"] += 1
            return m.group(0)

        boleh_perbaiki = (
            rendah[0] == diharapkan[0]
            and keadaan["panjang_runtun"] >= _MIN_RUNTUN_UNTUK_PERBAIKAN
        )
        if boleh_perbaiki:
            keadaan["terakhir"] = diharapkan
            keadaan["panjang_runtun"] += 1
            keadaan["diperbaiki"] += 1
            logger.info("Penanda daftar diperbaiki: '%s.' -> '%s.'", penanda, diharapkan)
            return f"{spasi_awal}{diharapkan}.{spasi_akhir}"

        keadaan["terakhir"] = rendah            # daftar lain — mulai runtun baru
        keadaan["panjang_runtun"] = 1
        return m.group(0)

    for halaman in pages_content:
        halaman["text"] = _POLA_PENANDA_HURUF.sub(tangani, halaman["text"])

    if keadaan["diperbaiki"]:
        logger.info(
            "%d penanda daftar dipulihkan — huruf ulangnya rontok saat OCR",
            keadaan["diperbaiki"],
        )
    return keadaan["diperbaiki"]


