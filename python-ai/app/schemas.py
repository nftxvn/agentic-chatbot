"""
Pydantic models (schemas) untuk validasi request dan response.
Digunakan oleh FastAPI untuk serialisasi/deserialisasi data.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Request Schemas ──────────────────────────────────────────────


class ProcessDocumentRequest(BaseModel):
    """Schema untuk request pemrosesan dokumen dari Laravel."""

    document_id: int = Field(..., description="ID dokumen dari database Laravel")
    file_path: str = Field(..., description="Path absolut ke file PDF")
    action: str = Field(
        ...,
        description="Aksi yang dilakukan: 'new' untuk dokumen baru, 'overwrite' untuk menimpa",
    )


class ChatRequest(BaseModel):
    """Schema untuk request chat streaming (SSE) dari pengguna."""

    session_id: str = Field(..., description="ID sesi chat pengguna")
    query: str = Field(..., description="Pertanyaan pengguna")
    document_ids: list[int] | None = Field(
        default=None,
        description=(
            "Batasi pencarian hanya pada dokumen tertentu. "
            "Kosongkan untuk mencari ke seluruh dokumen."
        ),
    )


class ChatMessageRequest(BaseModel):
    """Schema untuk request chat non-streaming (WhatsApp webhook)."""

    phone_number: str = Field(..., description="Nomor telepon pengguna WhatsApp")
    message: str = Field(..., description="Pesan/pertanyaan dari pengguna")
    document_ids: list[int] | None = Field(
        default=None,
        description=(
            "Batasi pencarian hanya pada dokumen tertentu. "
            "Kosongkan untuk mencari ke seluruh dokumen."
        ),
    )


# ── Response Schemas ─────────────────────────────────────────────


class ProcessDocumentResponse(BaseModel):
    """Schema untuk response setelah dokumen dikirim ke antrian."""

    status: str = Field(..., description="Status request: 'accepted', 'error'")
    message: str = Field(..., description="Pesan deskriptif tentang status")


class DocumentStatusResponse(BaseModel):
    """Schema untuk response status satu dokumen."""

    id: int
    status: str = Field(..., description="Status: pending, processing, completed, failed")
    pdf_type: Optional[str] = Field(None, description="Tipe PDF: text, scanned, mixed")
    total_pages: Optional[int] = None
    total_chunks: Optional[int] = None
    error_message: Optional[str] = None
    processed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DocumentListItem(BaseModel):
    """Schema untuk satu item dalam daftar dokumen."""

    id: int
    original_name: Optional[str] = None
    file_path: Optional[str] = None
    status: str = Field(..., description="Status: pending, processing, completed, failed")
    pdf_type: Optional[str] = None
    total_pages: Optional[int] = None
    total_chunks: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DocumentListResponse(BaseModel):
    """Schema untuk response daftar dokumen."""

    total: int = Field(..., description="Jumlah total dokumen")
    documents: list[DocumentListItem] = Field(..., description="Daftar dokumen")


class SourceReference(BaseModel):
    """Schema untuk referensi sumber dokumen dalam response chat."""

    doc_name: Optional[str] = None
    document_id: Optional[int] = None
    page: Optional[int] = None


class ChatMessageResponse(BaseModel):
    """Schema untuk response chat non-streaming (WhatsApp)."""

    reply: str = Field(..., description="Jawaban lengkap dari AI")
    sources: list[SourceReference] = Field(
        default_factory=list,
        description="Daftar sumber dokumen yang dirujuk",
    )
