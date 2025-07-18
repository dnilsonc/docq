from sqlalchemy import Column, String, DateTime, Text, JSON, Integer, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

Base = declarative_base()


class Document(Base):
    """Modelo para armazenar documentos processados"""

    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String(100))

    # Sessão temporária
    session_id = Column(String(36), nullable=False)  # UUID da sessão
    session_expires_at = Column(DateTime, nullable=False)  # Quando a sessão expira

    # Timestamps
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)

    # Texto extraído via OCR
    extracted_text = Column(Text)

    # Metadados extraídos via NLP (CNPJ, datas, valores, etc.)
    document_metadata = Column(JSON)

    # Status do processamento
    status = Column(
        String(50), default="uploading"
    )  # uploading -> processing -> indexed -> ready -> error

    # Configurações de processamento
    ocr_confidence = Column(JSON)  # scores de confiança do OCR
    processing_time = Column(Integer)  # tempo em segundos

    # Controle de versioning
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return (
            f"<Document(id={self.id}, filename={self.filename}, status={self.status})>"
        )


class DocumentChunk(Base):
    """Modelo para chunks de texto vetorizados"""

    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), nullable=False)

    # Conteúdo do chunk
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)  # ordem no documento

    # Metadados do chunk
    page_number = Column(Integer)
    bbox = Column(JSON)  # bounding box se disponível

    # ID do vetor no Qdrant
    vector_id = Column(String(100))

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<DocumentChunk(id={self.id}, doc_id={self.document_id}, chunk_index={self.chunk_index})>"
