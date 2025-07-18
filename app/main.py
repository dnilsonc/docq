import asyncio
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from pathlib import Path

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Depends,
    HTTPException,
    BackgroundTasks,
    Form,
)
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from loguru import logger
from db.session import get_db, create_tables
from db.models import Document
from storage.upload_handler import upload_handler
from app.ocr_pipeline import ocr_pipeline
from vectordb.indexer import vector_indexer
from app.rag_pipeline import rag_pipeline

# Inicializar FastAPI
app = FastAPI(
    title="DocQ - OCR & RAG API",
    description="API para processamento de documentos com OCR e sistema de perguntas e respostas",
    version="1.0.0",
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especificar domínios
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Modelos Pydantic para request/response
class DocumentResponse(BaseModel):
    id: str
    filename: str
    status: str
    uploaded_at: str
    processed_at: Optional[str] = None
    metadata: Optional[dict] = None
    processing_time: Optional[int] = None
    extracted_text: Optional[str] = None


class QuestionRequest(BaseModel):
    question: str
    session_id: str
    max_chunks: Optional[int] = 3
    document_id: Optional[str] = None


class QuestionResponse(BaseModel):
    answer: str
    sources: List[dict]
    confidence: float
    question: str
    timestamp: str


class SearchRequest(BaseModel):
    query: str
    session_id: str
    limit: int = 5
    score_threshold: float = 0.3


# Eventos de inicialização
@app.on_event("startup")
async def startup_event():
    """Inicializar banco de dados e verificar dependências"""
    try:
        logger.info("Iniciando aplicação DocQ...")

        # Criar tabelas do banco
        create_tables()
        logger.info("Tabelas do banco criadas/verificadas")

        # Verificar Qdrant
        try:
            collections = vector_indexer.client.get_collections()
            logger.info(f"Qdrant conectado. Coleções: {len(collections.collections)}")
        except Exception as e:
            logger.warning(f"Qdrant não disponível: {e}")

        logger.info("Aplicação iniciada com sucesso!")

    except Exception as e:
        logger.error(f"Erro na inicialização: {e}")
        raise


# Processamento em background
async def process_document_async(document_id: str, file_path: str):
    """Processar documento de forma assíncrona"""
    try:
        logger.info(f"Iniciando processamento async do documento {document_id}")

        # 1. Executar OCR
        ocr_result = ocr_pipeline.process_document(document_id, file_path)

        # 2. Indexar no banco vetorial
        if ocr_result["text"]:
            chunk_ids = vector_indexer.index_document(
                document_id=document_id,
                text=ocr_result["text"],
                metadata=ocr_result.get("metadata", {}),
            )

            # 3. Atualizar status final
            db = next(get_db())
            try:
                document = db.query(Document).filter(Document.id == document_id).first()
                if document:
                    document.status = "indexed"
                    db.commit()
                    logger.info(
                        f"Documento {document_id} indexado com {len(chunk_ids)} chunks"
                    )
            finally:
                db.close()

    except Exception as e:
        logger.error(f"Erro no processamento async do documento {document_id}: {e}")

        # Marcar como erro
        db = next(get_db())
        try:
            document = db.query(Document).filter(Document.id == document_id).first()
            if document:
                document.status = "error"
                document.document_metadata = {"error": str(e)}
                db.commit()
        finally:
            db.close()


# Rotas da API


@app.get("/", summary="Health Check")
async def root():
    """Verificar se a API está funcionando"""
    return {
        "message": "DocQ API está funcionando!",
        "version": "1.0.0",
        "timestamp": str(datetime.now()),
    }


@app.get("/health", summary="Status detalhado do sistema")
async def health_check():
    """Verificar status de todos os componentes"""
    status = {"api": "ok", "timestamp": str(datetime.now())}

    # Verificar banco de dados
    try:
        db = next(get_db())
        db.execute(text("SELECT 1"))
        status["database"] = "ok"
        db.close()
    except Exception as e:
        status["database"] = f"error: {e}"

    # Verificar Qdrant
    try:
        collections = vector_indexer.client.get_collections()
        status["qdrant"] = "ok"
        status["collections_count"] = len(collections.collections)
    except Exception as e:
        status["qdrant"] = f"error: {e}"

    # Verificar modelos OCR
    status["ocr"] = {
        "paddle_ocr": "ok",
        "trocr": "ok" if ocr_pipeline.trocr_available else "not_available",
    }

    # Verificar LLM
    status["llm"] = rag_pipeline.llm._llm_type

    return status


@app.post("/upload", response_model=DocumentResponse, summary="Upload de documento")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session_id: str = Form(...),
    session_expires_at: str = Form(...),
    db: Session = Depends(get_db),
):
    """Upload e processamento de documento PDF ou imagem com sessão"""

    try:
        # Gerar ID único para o documento
        document_id = str(uuid.uuid4())

        logger.info(
            f"Recebendo upload: {file.filename} (ID: {document_id}, Sessão: {session_id[:8]}...)"
        )

        # Converter string de data para datetime
        session_expires_datetime = datetime.fromisoformat(
            session_expires_at.replace("Z", "+00:00")
        )

        # Salvar arquivo
        file_info = upload_handler.save_file(file, document_id)

        # Criar registro no banco
        document = Document(
            id=document_id,
            filename=file_info["filename"],
            file_path=file_info["file_path"],
            file_size=file_info["size"],
            mime_type=file_info["mime_type"],
            session_id=session_id,
            session_expires_at=session_expires_datetime,
            status="uploading",
        )

        db.add(document)
        db.commit()

        # Adicionar processamento em background
        background_tasks.add_task(
            process_document_async, document_id, file_info["file_path"]
        )

        return DocumentResponse(
            id=document_id,
            filename=file_info["filename"],
            status="processing",
            uploaded_at=str(document.uploaded_at),
        )

    except Exception as e:
        logger.error(f"Erro no upload: {e}")
        raise HTTPException(status_code=500, detail=f"Erro no upload: {str(e)}")


@app.get(
    "/document/{document_id}",
    response_model=DocumentResponse,
    summary="Status do documento",
)
async def get_document_status(document_id: str, db: Session = Depends(get_db)):
    """Obter status e informações de um documento"""
    try:
        try:
            doc_uuid = uuid.UUID(document_id)
        except Exception:
            raise HTTPException(status_code=400, detail="ID de documento inválido")
        document = db.query(Document).filter(Document.id == doc_uuid).first()
        if not document:
            raise HTTPException(status_code=404, detail="Documento não encontrado")
        return DocumentResponse(
            id=str(document.id),
            filename=document.filename,
            status=document.status,
            uploaded_at=str(document.uploaded_at),
            processed_at=str(document.processed_at) if document.processed_at else None,
            metadata=document.document_metadata,
            processing_time=document.processing_time,
            extracted_text=document.extracted_text,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar documento {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Erro interno do servidor")


@app.get("/documents", summary="Listar documentos")
async def list_documents(
    session_id: str,
    limit: int = 10,
    offset: int = 0,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Listar documentos da sessão com paginação e filtros"""

    try:
        query = db.query(Document).filter(
            Document.is_active == True,
            Document.session_id == session_id,
            Document.session_expires_at > datetime.utcnow(),
        )

        if status:
            query = query.filter(Document.status == status)

        total = query.count()
        documents = query.offset(offset).limit(limit).all()

        return {
            "documents": [
                DocumentResponse(
                    id=str(doc.id),
                    filename=doc.filename,
                    status=doc.status,
                    uploaded_at=str(doc.uploaded_at),
                    processed_at=str(doc.processed_at) if doc.processed_at else None,
                    metadata=doc.document_metadata,
                    processing_time=doc.processing_time,
                )
                for doc in documents
            ],
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    except Exception as e:
        logger.error(f"Erro ao listar documentos: {e}")
        raise HTTPException(status_code=500, detail="Erro interno do servidor")


@app.post(
    "/ask", response_model=QuestionResponse, summary="Fazer pergunta sobre documentos"
)
async def ask_question(request: QuestionRequest, db: Session = Depends(get_db)):
    """Fazer pergunta sobre os documentos da sessão usando RAG"""

    try:
        logger.info(
            f"Recebendo pergunta: {request.question} (Sessão: {request.session_id[:8]}...)"
        )

        # Verificar se há documentos válidos na sessão
        valid_docs = (
            db.query(Document)
            .filter(
                Document.session_id == request.session_id,
                Document.session_expires_at > datetime.utcnow(),
                Document.is_active == True,
                Document.status.in_(["indexed", "ready"]),
            )
            .all()
        )

        if not valid_docs:
            raise HTTPException(
                status_code=404, detail="Nenhum documento válido encontrado na sessão"
            )

        if request.document_id:
            logger.info(f"Document ID recebido: {request.document_id}")
            # Verificar se o documento pertence à sessão
            doc_in_session = any(
                str(doc.id) == request.document_id for doc in valid_docs
            )
            if not doc_in_session:
                raise HTTPException(
                    status_code=403, detail="Documento não pertence à sessão atual"
                )
        else:
            logger.info(
                "Nenhum document_id especificado - buscando em todos os documentos da sessão"
            )

        # Processar pergunta usando RAG
        result = rag_pipeline.ask_question(
            question=request.question,
            max_chunks=request.max_chunks or 3,
            document_id=request.document_id,
            session_id=request.session_id,
        )

        return QuestionResponse(
            answer=result["answer"],
            sources=result["sources"],
            confidence=result["confidence"],
            question=request.question,
            timestamp=result["timestamp"],
        )

    except Exception as e:
        logger.error(f"Erro ao processar pergunta: {e}")
        raise HTTPException(
            status_code=500, detail=f"Erro ao processar pergunta: {str(e)}"
        )


@app.delete("/document/{document_id}", summary="Deletar documento")
async def delete_document(document_id: str, db: Session = Depends(get_db)):
    """Deletar documento e remover do índice vetorial"""
    try:
        try:
            doc_uuid = uuid.UUID(document_id)
        except Exception:
            raise HTTPException(status_code=400, detail="ID de documento inválido")
        document = db.query(Document).filter(Document.id == doc_uuid).first()
        if not document:
            raise HTTPException(status_code=404, detail="Documento não encontrado")
        # Remover arquivo do disco
        try:
            upload_handler.delete_file(document.file_path)
        except Exception as e:
            logger.warning(f"Erro ao remover arquivo: {e}")
        # Remover do índice vetorial
        try:
            vector_indexer.delete_document(document_id)
        except Exception as e:
            logger.warning(f"Erro ao remover do índice: {e}")
        # Marcar como inativo (soft delete)
        document.is_active = False
        db.commit()
        return {"message": "Documento removido com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao deletar documento {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Erro interno do servidor")


@app.post("/search", summary="Busca textual nos documentos")
async def search_documents(request: SearchRequest, db: Session = Depends(get_db)):
    """Buscar chunks de texto similares à consulta na sessão"""

    try:
        # Verificar se há documentos válidos na sessão
        valid_docs = (
            db.query(Document)
            .filter(
                Document.session_id == request.session_id,
                Document.session_expires_at > datetime.utcnow(),
                Document.is_active == True,
                Document.status.in_(["indexed", "ready"]),
            )
            .all()
        )

        if not valid_docs:
            return {"query": request.query, "results": [], "total_found": 0}

        # Obter IDs dos documentos válidos
        valid_doc_ids = [str(doc.id) for doc in valid_docs]

        results = vector_indexer.search_similar(
            query=request.query,
            limit=request.limit,
            score_threshold=request.score_threshold,
            session_doc_ids=valid_doc_ids,
        )

        return {"query": request.query, "results": results, "total_found": len(results)}

    except Exception as e:
        logger.error(f"Erro na busca: {e}")
        raise HTTPException(status_code=500, detail="Erro na busca")


@app.post("/cleanup", summary="Limpeza de sessões expiradas")
async def cleanup_expired_sessions(db: Session = Depends(get_db)):
    """Remove documentos de sessões expiradas"""

    try:
        # Encontrar documentos de sessões expiradas
        expired_docs = (
            db.query(Document)
            .filter(
                Document.session_expires_at <= datetime.utcnow(),
                Document.is_active == True,
            )
            .all()
        )

        cleanup_count = 0
        for document in expired_docs:
            try:
                # Remover arquivo do disco
                upload_handler.delete_file(document.file_path)

                # Remover do índice vetorial
                vector_indexer.delete_document(str(document.id))

                # Marcar como inativo (soft delete)
                document.is_active = False
                cleanup_count += 1

            except Exception as e:
                logger.warning(f"Erro ao limpar documento {document.id}: {e}")

        db.commit()

        logger.info(f"Cleanup concluído: {cleanup_count} documentos removidos")

        return {
            "message": "Limpeza concluída",
            "documents_cleaned": cleanup_count,
            "timestamp": str(datetime.utcnow()),
        }

    except Exception as e:
        logger.error(f"Erro no cleanup: {e}")
        raise HTTPException(status_code=500, detail="Erro na limpeza")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
