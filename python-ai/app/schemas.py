"""
Pydantic models (schemas) untuk validasi request dan response.
Digunakan oleh FastAPI untuk serialisasi/deserialisasi data.
"""

from pydantic import BaseModel, Field


class ProcessDocumentRequest(BaseModel):
    """Schema untuk request pemrosesan dokumen dari Laravel."""

    document_id: int = Field(..., description="ID dokumen dari database Laravel")
    file_path: str = Field(..., description="Path absolut ke file PDF")
    action: str = Field(
        ...,
        description="Aksi yang dilakukan: 'new' untuk dokumen baru, 'overwrite' untuk menimpa",
    )


class ChatRequest(BaseModel):
    """Schema untuk request chat dari pengguna."""

    session_id: str = Field(..., description="ID sesi chat pengguna")
    query: str = Field(..., description="Pertanyaan pengguna")


class ProcessDocumentResponse(BaseModel):
    """Schema untuk response setelah dokumen dikirim ke antrian."""

    status: str = Field(..., description="Status request: 'accepted', 'error'")
    message: str = Field(..., description="Pesan deskriptif tentang status")
