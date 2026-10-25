"""Orkestrasi halaman native, gambar tertanam, OCR, dan pewarisan petunjuk."""

import base64
import logging
from typing import Any, Callable

from app.services.ocr.pdf_io import (
    fitz,
    _resolve_pdf_path,
    _extract_text_from_page,
    _MIN_TEXT_LENGTH,
)
from app.services.ocr.prompts import _PETUNJUK_TABEL_SOP, _PETUNJUK_KEPALA_SOP
from app.services.ocr.vision import vision_extract_general
from app.services.ocr.sop import (
    _kepala_sop_terlihat,
    _terlihat_formulir_sop,
    _ocr_dengan_penjaga,
)
from app.services.ocr.cleanup import perbaiki_penanda_daftar

logger = logging.getLogger("app.services.pdf_processor")

def _ekstrak_gambar_tersemat(
    page: "fitz.Page",
    nomor: int,
    category_prompt: str | None = None,
    job_titles: str | None = None,
    vision_model: str | None = None,
    custom_prompts: dict | None = None,
) -> str:
    """
    Mengekstrak teks/bagan dari gambar signifikan yang tertanam pada halaman teks digital.
    Mengabaikan logo kecil, ikon, kop surat, atau hiasan berukuran kecil.
    """
    try:
        image_list = page.get_images(full=True)
    except Exception:
        return ""

    if not image_list:
        return ""

    page_area = max(page.rect.width * page.rect.height, 1.0)
    extracted_sections = []
    seen_xrefs = set()

    for img_info in image_list:
        xref = img_info[0]
        if xref in seen_xrefs:
            continue
        seen_xrefs.add(xref)

        w, h = img_info[2], img_info[3]
        # Abaikan gambar kecil (ikon, garis, ornamen)
        if w < 250 or h < 180 or (w * h < 50000):
            continue

        rects = page.get_image_rects(xref)
        is_significant = False
        if rects:
            for r in rects:
                area_ratio = (r.width * r.height) / page_area
                if area_ratio >= 0.10 or (r.width >= 200 and r.height >= 150):
                    is_significant = True
                    break
        else:
            if w >= 350 and h >= 250:
                is_significant = True

        if not is_significant:
            continue

        logger.info(
            "Halaman %d: Menemukan gambar/bagan tertanam (xref=%d, %dx%d px), mengekstrak via Vision AI...",
            nomor, xref, w, h,
        )

        try:
            doc = page.parent
            base_img = doc.extract_image(xref)
            img_bytes = base_img.get("image")
            if not img_bytes:
                continue

            import io
            from PIL import Image
            img = Image.open(io.BytesIO(img_bytes))
            MAX_DIM = 2048
            if max(img.size) > MAX_DIM:
                scale = MAX_DIM / max(img.size)
                new_size = (int(img.width * scale), int(img.height * scale))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            buf = io.BytesIO()
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(buf, format="JPEG", quality=85)
            img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

            prompt_diagram = (
                "Anda adalah sistem OCR cerdas. Ekstrak dan salin SELURUH teks, bagan alur, diagram, "
                "atau tabel yang terdapat di dalam gambar ini secara terstruktur dan lengkap. "
                "Sajikan hasilnya apa adanya tanpa asumsi atau ringkasan di luar yang terlihat pada gambar."
            )

            res = vision_extract_general(
                img_b64,
                petunjuk=prompt_diagram,
                category_prompt=category_prompt,
                job_titles=job_titles,
                vision_model=vision_model,
                custom_prompts=custom_prompts,
            )
            if res and len(res.strip()) > 20:
                extracted_sections.append(res.strip())
        except Exception as err:
            logger.warning("Halaman %d: Gagal mengekstrak gambar xref=%d: %s", nomor, xref, err)

    if extracted_sections:
        return "\n\n---\n### [Konten Gambar / Bagan Terlampir]:\n" + "\n\n".join(extracted_sections)
    return ""


def _ekstrak_halaman(
    page: "fitz.Page",
    nomor: int,
    petunjuk_tabel: str | None,
    category_prompt: str | None = None,
    job_titles: str | None = None,
    vision_model: str | None = None,
    custom_prompts: dict | None = None,
) -> tuple[str, str | None]:
    """
    Ekstrak SATU halaman. Satu-satunya tempat logika per halaman ditulis.
    """
    text = _extract_text_from_page(page)
    if len(text) >= _MIN_TEXT_LENGTH:
        tambahan_gambar = _ekstrak_gambar_tersemat(
            page,
            nomor,
            category_prompt=category_prompt,
            job_titles=job_titles,
            vision_model=vision_model,
            custom_prompts=custom_prompts,
        )
        if tambahan_gambar:
            text = text + tambahan_gambar
        return text, petunjuk_tabel

    logger.info(
        "Halaman %d: teks minim (%d karakter), memulai vision pipeline umum...",
        nomor, len(text),
    )

    rect = page.rect
    max_side = max(rect.width, rect.height)
    zoom = 1.5
    if max_side * zoom > 2048:
        zoom = max(2048.0 / max_side, 0.5)
    pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    img_base64 = base64.b64encode(pixmap.tobytes("jpeg", jpg_quality=85)).decode("utf-8")

    tabel_rule = (custom_prompts.get("tabel_sop") if custom_prompts else None) or _PETUNJUK_TABEL_SOP
    kepala_rule = (custom_prompts.get("kepala_sop") if custom_prompts else None) or _PETUNJUK_KEPALA_SOP

    petunjuk_awal = petunjuk_tabel
    text = vision_extract_general(
        img_base64,
        petunjuk=petunjuk_tabel,
        category_prompt=category_prompt,
        job_titles=job_titles,
        vision_model=vision_model,
        custom_prompts=custom_prompts,
    )

    kepala = kepala_rule if _kepala_sop_terlihat(text) else ""

    if petunjuk_tabel is None and _terlihat_formulir_sop(text):
        logger.info(
            "Halaman %d terdeteksi berformat formulir SOP — petunjuk tabel "
            "prosedur diaktifkan untuk halaman berikutnya.",
            nomor,
        )
        petunjuk_tabel = tabel_rule

    petunjuk_penuh = (petunjuk_tabel or "") + kepala
    if petunjuk_penuh and petunjuk_penuh != (petunjuk_awal or ""):
        if kepala:
            logger.info(
                "Halaman %d memuat kepala formulir — dibaca ulang dengan "
                "petunjuk kepala.",
                nomor,
            )
        text = _ocr_dengan_penjaga(
            img_base64,
            nomor,
            petunjuk_penuh,
            category_prompt=category_prompt,
            job_titles=job_titles,
            vision_model=vision_model,
            custom_prompts=custom_prompts,
        )

    return text, petunjuk_tabel


def ekstrak_gambar_uji(
    img_base64: str,
    category_prompt: str | None = None,
    job_titles: str | None = None,
    vision_model: str | None = None,
    custom_prompts: dict | None = None,
) -> dict:
    """
    Jalankan SATU gambar lepas lewat jalur vision yang sama persis dengan produksi.

    Ada supaya sandbox "Uji Prompt" di admin tidak lagi punya implementasi
    sendiri. Sebelumnya sandbox memakai prompt kategori sebagai PENGGANTI aturan
    dasar dan tidak punya deteksi formulir SOP sama sekali — sehingga hasil uji
    bisa jauh berbeda dari hasil ekstraksi sungguhan, dan admin menyetel
    promptnya berdasarkan hasil yang menyesatkan.

    Satu perbedaan tetap ada dan memang tidak terhindarkan: di produksi petunjuk
    tabel SOP menempel antar halaman (halaman lanjutan mewarisi dari halaman
    sebelumnya), sedangkan di sini hanya ada satu gambar sehingga deteksinya
    berlaku untuk gambar itu saja. Itu dilaporkan lewat `petunjuk_aktif` supaya
    terlihat, bukan disembunyikan.

    Returns:
        dict berisi `teks` (hasil akhir), `teks_awal` (bacaan pertama sebelum
        petunjuk otomatis dipasang), dan `petunjuk_aktif` (daftar nama petunjuk
        yang menyala).
    """
    tabel_rule = (custom_prompts.get("tabel_sop") if custom_prompts else None) or _PETUNJUK_TABEL_SOP
    kepala_rule = (custom_prompts.get("kepala_sop") if custom_prompts else None) or _PETUNJUK_KEPALA_SOP

    teks_awal = vision_extract_general(
        img_base64,
        category_prompt=category_prompt,
        job_titles=job_titles,
        vision_model=vision_model,
        custom_prompts=custom_prompts,
    )

    # Urutan pemeriksaannya sama dengan _ekstrak_satu_halaman: petunjuk dipilih
    # dari ISI bacaan pertama, bukan dari setelan kategori.
    tabel = tabel_rule if _terlihat_formulir_sop(teks_awal) else ""
    kepala = kepala_rule if _kepala_sop_terlihat(teks_awal) else ""

    aktif = []
    if tabel:
        aktif.append("tabel prosedur SOP")
    if kepala:
        aktif.append("kepala formulir SOP")

    teks = teks_awal
    petunjuk_penuh = tabel + kepala
    if petunjuk_penuh:
        teks = _ocr_dengan_penjaga(
            img_base64,
            1,
            petunjuk_penuh,
            category_prompt=category_prompt,
            job_titles=job_titles,
            vision_model=vision_model,
            custom_prompts=custom_prompts,
        )

    return {"teks": teks, "teks_awal": teks_awal, "petunjuk_aktif": aktif}


def ekstrak_satu_halaman(
    file_path: str,
    page_number: int,
    petunjuk_tabel: str | None = None,
    category_prompt: str | None = None,
    job_titles: str | None = None,
    vision_model: str | None = None,
    custom_prompts: dict | None = None,
) -> tuple[str, str | None]:
    """
    Ekstrak satu halaman, membawa petunjuk format dari panggilan sebelumnya.
    """
    file_path = _resolve_pdf_path(file_path)

    with fitz.open(file_path) as doc:
        if not 1 <= page_number <= len(doc):
            raise ValueError(
                f"Halaman {page_number} di luar jangkauan "
                f"(dokumen ini {len(doc)} halaman)"
            )
        return _ekstrak_halaman(
            doc[page_number - 1],
            page_number,
            petunjuk_tabel,
            category_prompt=category_prompt,
            job_titles=job_titles,
            vision_model=vision_model,
            custom_prompts=custom_prompts,
        )


def extract_text(
    file_path: str,
    page_num: int | None = None,
    progress_callback: Callable | None = None,
) -> list[dict]:
    """
    Mengekstrak teks dari seluruh halaman PDF.
    - Halaman teks: PyMuPDF langsung.
    - Halaman scan: Ekstrak menggunakan Ollama Vision Model secara umum.
    """
    file_path = _resolve_pdf_path(file_path)

    from app.services.document_operations import DocumentOperationCancelled

    pages_content: list[dict] = []
    doc = None

    try:
        doc = fitz.open(file_path)
        total_pages = len(doc)
        if page_num is not None:
            pages_to_process = [page_num]
            logger.info("Memproses PDF '%s' (hanya halaman %d)", file_path, page_num + 1)
        else:
            pages_to_process = list(range(total_pages))
            logger.info("Memproses PDF '%s' (%d halaman)", file_path, total_pages)

        # Petunjuk format ditemukan dari dokumennya sendiri, bukan diandaikan.
        petunjuk_tabel: str | None = None

        for count, p_idx in enumerate(pages_to_process, start=1):
            if p_idx >= total_pages:
                logger.warning(f"Halaman {p_idx + 1} di luar jangkauan (total {total_pages}).")
                continue

            text, petunjuk_tabel = _ekstrak_halaman(
                doc[p_idx], p_idx + 1, petunjuk_tabel
            )

            if text:
                pages_content.append({
                    "page_number": p_idx + 1,
                    "text": text,
                })

            if progress_callback is not None:
                try:
                    progress_callback(count, total_pages, p_idx + 1, text)
                except DocumentOperationCancelled:
                    raise
                except TypeError:
                    try:
                        progress_callback(count, total_pages)
                    except DocumentOperationCancelled:
                        raise
                    except Exception as cb_err:
                        logger.warning("Error saat memanggil progress_callback: %s", cb_err)
                except Exception as cb_err:
                    logger.warning("Error saat memanggil progress_callback: %s", cb_err)

        # Dijalankan setelah SELURUH halaman terkumpul: daftar menyeberang
        # halaman, jadi penanda pertama sebuah halaman hanya bisa disimpulkan
        # dari penanda terakhir halaman sebelumnya.
        perbaiki_penanda_daftar(pages_content)

        logger.info("Berhasil mengekstrak teks dari %d/%d halaman PDF '%s'", len(pages_content), total_pages, file_path)
        return pages_content

    except DocumentOperationCancelled:
        raise
    except Exception as e:
        logger.error("Gagal mengekstrak teks dari PDF '%s': %s", file_path, str(e))
        raise
    finally:
        if doc is not None:
            doc.close()


