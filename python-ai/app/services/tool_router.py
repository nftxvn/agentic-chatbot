"""
Service untuk routing intent pengguna ke tool/handler yang sesuai.

Saat ini (MVP), semua query diarahkan ke RAG.
Di masa depan, service ini akan menggunakan semantic routing atau
tool calling untuk mengarahkan query ke handler yang tepat
(misalnya: cek tiket, buat tiket, RAG, dsb.).
"""

import logging

logger = logging.getLogger(__name__)


def route_intent(query: str) -> str:
    """
    Menentukan intent dari query pengguna dan mengembalikan
    nama handler yang sesuai.

    Saat ini (MVP), selalu mengembalikan 'rag' karena fitur
    pengecekan tiket belum termasuk dalam scope.

    Args:
        query: Pertanyaan atau perintah dari pengguna.

    Returns:
        String nama handler: 'rag' (untuk saat ini).

    TODO: Implementasi semantic routing di versi mendatang.
          Rencana pengembangan:
          1. Gunakan classifier atau embedding-based routing untuk
             mendeteksi intent (misalnya: 'check_ticket', 'create_ticket',
             'rag', 'general_chat').
          2. Integrasikan dengan LLM tool calling / function calling
             untuk routing yang lebih cerdas.
          3. Tambahkan fallback mechanism jika intent tidak terdeteksi.

    Contoh intent yang akan didukung:
        - 'rag'          : Pertanyaan berdasarkan dokumen knowledge base.
        - 'check_ticket' : Cek status tiket IT support.
        - 'create_ticket': Buat tiket IT support baru.
        - 'escalate'     : Eskalasi masalah ke teknisi.
    """
    logger.debug("Routing intent untuk query: '%s' -> 'rag'", query[:80])

    # MVP: Semua query diarahkan ke RAG
    return "rag"
