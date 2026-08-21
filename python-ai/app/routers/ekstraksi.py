"""
Endpoint kendali ekstraksi bertahap: mulai, jeda, lanjut, koreksi, simpan.

Alur yang dilayani berkas ini punya dua gerbang manual. Sistem berhenti sendiri
dan menunggu manusia di keduanya:

    unggah -> ekstraksi (bisa dijeda) -> KOREKSI -> pratinjau -> SIMPAN -> selesai

Tidak ada tahap yang berjalan otomatis setelah tahap sebelumnya selesai. Hasil
OCR dokumen pindaian tidak layak masuk korpus tanpa diperiksa mata manusia, dan
embedding adalah satu-satunya langkah yang mahal sekaligus mengganti isi korpus
— jadi hanya itu yang dijaga tombol.
"""

import json
import logging

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sse_starlette.sse import EventSourceResponse

from app.database import get_document_by_id
from app.routers.documents import verify_token
from app.services import ekstraksi_bertahap as eb

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/docs", tags=["Ekstraksi"])

_ERROR_MESSAGE = "Terjadi kesalahan internal. Rinciannya tercatat di log server."

# Jeda antar kabar pada aliran SSE. Dua detik: cukup rapat agar bilah kemajuan
# terasa hidup, cukup renggang agar 171 halaman tidak menghasilkan ribuan
# kabar yang isinya sama.
_JEDA_ALIRAN_DETIK = 2.0


def _dokumen_atau_404(document_id: int) -> dict:
    dokumen = get_document_by_id(document_id)
    if dokumen is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dokumen {document_id} tidak ditemukan",
        )
    if not dokumen.get("file_path"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dokumen {document_id} tidak punya berkas",
        )
    return dokumen


def _penyimpanan() -> "eb.PenyimpananMySQL":
    return eb.PenyimpananMySQL()


# ── POST /{id}/ekstraksi — Mulai atau lanjutkan ──────────────────


@router.post(
    "/{document_id}/ekstraksi",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Mulai atau lanjutkan ekstraksi",
)
async def mulai_ekstraksi(
    document_id: int,
    maks_halaman: int | None = Body(default=None, embed=True),
    _token: str = Depends(verify_token),
) -> dict:
    """
    Satu endpoint untuk mulai DAN lanjut — keduanya memang operasi yang sama.

    Halaman yang sudah tersimpan dilewati otomatis, jadi pemanggil tidak perlu
    melacak sendiri apakah ini pekerjaan baru atau penerusan. Menyediakan dua
    endpoint terpisah hanya menambah satu keadaan yang bisa salah dipilih.
    """
    dokumen = _dokumen_atau_404(document_id)

    from app.tasks.ekstraksi import ekstrak_dokumen_task

    ekstrak_dokumen_task.delay(document_id, dokumen["file_path"], maks_halaman)
    logger.info("Dokumen %d: ekstraksi diantrekan", document_id)

    return {"document_id": document_id, "status": eb.STATUS_ANTRE}


# ── POST /{id}/ekstraksi/jeda — Minta berhenti ───────────────────


@router.post(
    "/{document_id}/ekstraksi/jeda",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Minta ekstraksi berhenti di batas halaman berikutnya",
)
async def jeda_ekstraksi(
    document_id: int,
    _token: str = Depends(verify_token),
) -> dict:
    """
    Jeda adalah PERMINTAAN, bukan penghentian seketika.

    Satu panggilan model vision berlangsung 20-60 detik dan tidak bisa dipotong
    di tengah tanpa menyisakan halaman separuh. Jadi benderanya dinyalakan di
    sini, lalu diperiksa worker di antara halaman: halaman yang sedang berjalan
    diselesaikan dan disimpan dulu, baru berhenti.

    Akibatnya untuk antarmuka: status BELUM langsung `jeda`. Ia masih
    `berjalan` dengan `jeda_diminta: true` sampai halaman itu tuntas.
    Tampilkan "Menjeda..." selama masa itu — kalau tombolnya langsung berkata
    "Terjeda", pengguna akan mengira sistemnya macet.
    """
    _dokumen_atau_404(document_id)
    _penyimpanan().minta_jeda(document_id)
    logger.info("Dokumen %d: jeda diminta", document_id)

    return {"document_id": document_id, "jeda_diminta": True}


# ── GET /{id}/ekstraksi — Keadaan sekarang ───────────────────────


@router.get("/{document_id}/ekstraksi", summary="Status dan kemajuan ekstraksi")
async def status_ekstraksi(
    document_id: int,
    _token: str = Depends(verify_token),
) -> dict:
    _dokumen_atau_404(document_id)

    keadaan = _penyimpanan().keadaan(document_id)
    if keadaan is None:
        # Dokumen ada tapi belum pernah diekstrak — bukan galat, hanya keadaan
        # awal. Mengembalikan 404 di sini memaksa Dev 2 menangani dua cabang
        # untuk satu hal yang sama.
        return {
            "document_id": document_id,
            "status": eb.STATUS_ANTRE,
            "jeda_diminta": False,
            "halaman_total": 0,
            "halaman_selesai": 0,
            "persen": 0,
            "pesan": None,
        }
    return keadaan


# ── GET /{id}/ekstraksi/aliran — Kemajuan langsung (SSE) ─────────


@router.get(
    "/{document_id}/ekstraksi/aliran",
    summary="Kemajuan ekstraksi secara langsung",
)
async def aliran_ekstraksi(
    document_id: int,
    _token: str = Depends(verify_token),
):
    """
    Aliran ditutup sendiri begitu pekerjaannya berhenti — selesai, dijeda,
    menunggu koreksi, atau gagal. Aliran yang dibiarkan terbuka selamanya
    menahan koneksi dan worker untuk keadaan yang tidak akan berubah lagi.
    """
    _dokumen_atau_404(document_id)
    penyimpanan = _penyimpanan()

    async def kabar():
        import asyncio

        BERHENTI = {
            eb.STATUS_JEDA,
            eb.STATUS_MENUNGGU_KOREKSI,
            eb.STATUS_SELESAI,
            eb.STATUS_GAGAL,
        }
        terakhir = None

        while True:
            keadaan = penyimpanan.keadaan(document_id) or {
                "status": eb.STATUS_ANTRE,
                "halaman_selesai": 0,
                "halaman_total": 0,
                "persen": 0,
            }

            # Hanya kirim bila ada yang berubah. Bilah kemajuan yang menerima
            # kabar identik tiap dua detik tidak lebih informatif, hanya lebih
            # berisik.
            sidik = (keadaan["status"], keadaan["halaman_selesai"])
            if sidik != terakhir:
                terakhir = sidik
                yield json.dumps(
                    {"type": "kemajuan", "content": keadaan}, ensure_ascii=False
                )

            if keadaan["status"] in BERHENTI:
                yield json.dumps(
                    {"type": "selesai", "content": keadaan["status"]},
                    ensure_ascii=False,
                )
                return

            await asyncio.sleep(_JEDA_ALIRAN_DETIK)

    return EventSourceResponse(kabar(), media_type="text/event-stream")


# ── GET /{id}/halaman — Teks semua halaman (untuk editor) ────────


@router.get("/{document_id}/halaman", summary="Teks halaman untuk editor koreksi")
async def daftar_halaman(
    document_id: int,
    perlu_diperiksa: bool = False,
    _token: str = Depends(verify_token),
) -> dict:
    """
    Dengan `perlu_diperiksa=1`, hanya halaman yang ditandai mencurigakan yang
    dikembalikan, beserta alasannya.

    Triase inilah yang membuat 171 halaman masuk akal dikoreksi manusia. Tanpa
    urutan yang menempatkan halaman bermasalah di depan, memeriksa satu per
    satu terasa mustahil dan pada akhirnya dilewati — yang sama saja dengan
    tidak punya tahap koreksi.
    """
    _dokumen_atau_404(document_id)

    from app.services.pdf_processor import _bagian_kepala_hilang, _header_sop_tidak_lengkap

    halaman = _penyimpanan().teks_terkumpul(document_id)

    if perlu_diperiksa:
        curiga = [
            {
                "page_number": h["page_number"],
                "alasan": f"{_bagian_kepala_hilang(h['text'])} hilang",
            }
            for h in halaman
            if _header_sop_tidak_lengkap(h["text"])
        ]
        return {
            "document_id": document_id,
            "jumlah": len(curiga),
            "halaman": curiga,
        }

    return {
        "document_id": document_id,
        "jumlah": len(halaman),
        "halaman": halaman,
    }


# ── PUT /{id}/halaman/{n} — Simpan koreksi satu halaman ──────────


@router.put("/{document_id}/halaman/{page_number}", summary="Simpan koreksi satu halaman")
async def simpan_koreksi(
    document_id: int,
    page_number: int,
    text: str = Body(..., embed=True),
    _token: str = Depends(verify_token),
) -> dict:
    """
    Menyimpan per halaman, bukan seluruh dokumen sekaligus.

    Halaman pindaian menghasilkan teks panjang; mengirim 171 halaman tiap kali
    menyimpan membuat satu kesalahan jaringan bisa menimpa pekerjaan berjam-jam.
    """
    _dokumen_atau_404(document_id)

    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Teks halaman tidak boleh kosong. Halaman kosong lenyap dari "
                "korpus tanpa galat, dan baru ketahuan lewat jawaban "
                "'tidak ditemukan'."
            ),
        )

    _penyimpanan().simpan_halaman(document_id, page_number, text)
    logger.info("Dokumen %d halaman %d dikoreksi (%d huruf)", document_id, page_number, len(text))

    return {"document_id": document_id, "page_number": page_number, "tersimpan": True}


# ── GET /{id}/potongan — Pratinjau induk/anak ────────────────────


@router.get("/{document_id}/potongan", summary="Pratinjau potongan induk dan anak")
async def pratinjau_potongan(
    document_id: int,
    _token: str = Depends(verify_token),
) -> dict:
    """
    Dihitung saat diminta, tidak disimpan.

    Pemotongan adalah fungsi murni dari teksnya: teks yang sama selalu
    menghasilkan potongan yang sama, dan biayanya milidetik. Menyimpannya
    justru menciptakan masalah — potongan yang dibuat dari teks versi lama,
    tetap tampak sah, dan masuk korpus tanpa ada yang menyadari selisihnya.
    """
    _dokumen_atau_404(document_id)

    from app.services import embedding_service

    halaman = _penyimpanan().teks_terkumpul(document_id)
    if not halaman:
        return {"document_id": document_id, "induk": [], "anak": [], "siap": False}

    judul = embedding_service.derive_document_title(halaman)
    induk, anak = embedding_service.chunk_text_hierarchical(halaman, document_title=judul)

    return {
        "document_id": document_id,
        "judul": judul,
        "jumlah_induk": len(induk),
        "jumlah_anak": len(anak),
        "induk": induk,
        "anak": anak,
        "siap": True,
    }


# ── POST /{id}/simpan — Tombol akhir: potong lalu embed ──────────


@router.post(
    "/{document_id}/simpan",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Potong lalu simpan vektornya ke korpus",
)
async def simpan_ke_korpus(
    document_id: int,
    _token: str = Depends(verify_token),
) -> dict:
    """
    Satu-satunya langkah yang dijaga tombol, karena satu-satunya yang mahal
    sekaligus mengganti isi korpus.

    Potongannya dihitung ulang di dalam tugas, bukan diambil dari pratinjau
    yang mungkin dilihat berjam-jam sebelumnya. Dengan begitu yang masuk korpus
    selalu berasal dari teks yang berlaku sekarang.
    """
    _dokumen_atau_404(document_id)

    keadaan = _penyimpanan().keadaan(document_id)
    if keadaan is None or keadaan["halaman_selesai"] == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dokumen ini belum punya halaman terekstrak",
        )

    if keadaan["status"] == eb.STATUS_BERJALAN:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Ekstraksi masih berjalan. Tunggu sampai selesai atau jeda "
                "dulu sebelum menyimpan ke korpus."
            ),
        )

    from app.tasks.ekstraksi import potong_dan_embed_task

    potong_dan_embed_task.delay(document_id)
    logger.info("Dokumen %d: potong & embed diantrekan", document_id)

    return {"document_id": document_id, "status": "diantrekan"}
