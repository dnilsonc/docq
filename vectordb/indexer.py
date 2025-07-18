import os
import uuid
from typing import List, Dict, Optional
from datetime import datetime

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from qdrant_client.http import models

from loguru import logger
from db.models import DocumentChunk
from db.session import SessionLocal


class VectorIndexer:
    """Indexador vetorial para documentos usando Qdrant"""

    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        qdrant_api_key: Optional[str] = None,
        collection_name: str = "documents",
    ):

        # Inicializar cliente Qdrant
        self.client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

        self.collection_name = collection_name

        # Inicializar modelo de embeddings
        self.embedding_model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2"
        )
        self.vector_dim = self.embedding_model.get_sentence_embedding_dimension()

        # Configurações de chunking
        self.chunk_size = int(os.getenv("CHUNK_SIZE", 300))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", 50))

        # Criar coleção se não existir
        self._ensure_collection()

        logger.info(f"VectorIndexer inicializado com modelo {self.embedding_model}")

    def _ensure_collection(self):
        """Garantir que a coleção existe no Qdrant"""

        try:
            collections = self.client.get_collections().collections
            collection_names = [col.name for col in collections]

            if self.collection_name not in collection_names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_dim, distance=Distance.COSINE
                    ),
                )
                logger.info(f"Coleção '{self.collection_name}' criada no Qdrant")
            else:
                logger.info(f"Coleção '{self.collection_name}' já existe")

        except Exception as e:
            logger.error(f"Erro ao verificar/criar coleção: {e}")
            raise

    def create_chunks(self, text: str) -> List[str]:
        """Dividir texto em chunks menores"""

        if not text or len(text.strip()) == 0:
            return []

        # Dividir por sentenças primeiro (usando pontos)
        sentences = text.replace("\n", " ").split(".")

        chunks = []
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Se adicionar essa sentença não ultrapassar o limite
            if len(current_chunk + sentence) <= self.chunk_size:
                current_chunk += sentence + ". "
            else:
                # Salvar chunk atual se não estiver vazio
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())

                # Iniciar novo chunk
                current_chunk = sentence + ". "

        # Adicionar último chunk se não estiver vazio
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        # Se não conseguiu dividir por sentenças, usar divisão simples por caracteres
        if not chunks and text:
            for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
                chunk = text[i : i + self.chunk_size]
                if chunk.strip():
                    chunks.append(chunk.strip())

        logger.info(f"Texto dividido em {len(chunks)} chunks")
        return chunks

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Gerar embeddings para uma lista de textos"""

        try:
            embeddings = self.embedding_model.encode(texts, convert_to_tensor=False)
            return embeddings.tolist() if hasattr(embeddings, "tolist") else embeddings
        except Exception as e:
            logger.error(f"Erro ao gerar embeddings: {e}")
            return []

    def index_document(
        self, document_id: str, text: str, metadata: Dict = None
    ) -> List[str]:
        """Indexar documento completo dividindo em chunks"""

        try:
            logger.info(f"Iniciando indexação do documento {document_id}")

            # 1. Criar chunks
            chunks = self.create_chunks(text)

            if not chunks:
                logger.warning(f"Nenhum chunk criado para documento {document_id}")
                return []

            # 2. Gerar embeddings
            embeddings = self.generate_embeddings(chunks)

            if len(embeddings) != len(chunks):
                logger.error(
                    f"Mismatch entre chunks ({len(chunks)}) e embeddings ({len(embeddings)})"
                )
                return []

            # 3. Preparar pontos para o Qdrant
            points = []
            chunk_ids = []

            db = SessionLocal()
            try:
                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                    # Gerar ID único para o chunk
                    chunk_id = str(uuid.uuid4())
                    chunk_ids.append(chunk_id)

                    # Criar payload com metadados
                    payload = {
                        "document_id": document_id,
                        "chunk_text": chunk,
                        "chunk_index": i,
                        "metadata": metadata or {},
                    }

                    # Criar ponto vetorial
                    point = PointStruct(id=chunk_id, vector=embedding, payload=payload)
                    points.append(point)

                    # Salvar chunk no banco
                    db_chunk = DocumentChunk(
                        id=chunk_id,
                        document_id=document_id,
                        chunk_text=chunk,
                        chunk_index=i,
                        vector_id=chunk_id,
                    )
                    db.add(db_chunk)

                # 4. Inserir pontos no Qdrant
                self.client.upsert(collection_name=self.collection_name, points=points)

                # 5. Commit no banco
                db.commit()

                logger.info(
                    f"Documento {document_id} indexado com {len(chunks)} chunks"
                )
                return chunk_ids

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Erro ao indexar documento {document_id}: {e}")
            raise

    def search_similar(
        self,
        query: str,
        limit: int = 5,
        score_threshold: float = 0.7,
        document_id: Optional[str] = None,
        session_doc_ids: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Buscar chunks similares à consulta"""

        try:
            # Gerar embedding da consulta
            query_embedding = self.embedding_model.encode([query])[0].tolist()

            # Preparar filtro por documento se especificado
            query_filter = None
            if document_id:
                query_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        )
                    ]
                )
            elif session_doc_ids:
                # Filtrar por documentos da sessão
                query_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchAny(any=session_doc_ids),
                        )
                    ]
                )

            # Buscar pontos similares
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=query_filter,
            )

            # Formatar resultados
            results = []
            for hit in search_result:
                results.append(
                    {
                        "chunk_id": hit.id,
                        "score": hit.score,
                        "document_id": hit.payload["document_id"],
                        "chunk_text": hit.payload["chunk_text"],
                        "chunk_index": hit.payload["chunk_index"],
                        "metadata": hit.payload.get("metadata", {}),
                    }
                )

            doc_info = f" no documento {document_id}" if document_id else ""
            logger.info(
                f"Busca retornou {len(results)} resultados para: '{query[:50]}...'{doc_info}"
            )
            return results

        except Exception as e:
            logger.error(f"Erro na busca vetorial: {e}")
            return []

    def delete_document(self, document_id: str) -> bool:
        """Remover todos os chunks de um documento"""

        try:
            # Buscar pontos do documento
            search_result = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        )
                    ]
                ),
            )

            # Extrair IDs dos pontos
            point_ids = [point.id for point in search_result[0]]

            if point_ids:
                # Deletar pontos do Qdrant
                self.client.delete(
                    collection_name=self.collection_name,
                    points_selector=models.PointIdsList(points=point_ids),
                )

                # Deletar chunks do banco
                db = SessionLocal()
                try:
                    db.query(DocumentChunk).filter(
                        DocumentChunk.document_id == document_id
                    ).delete()
                    db.commit()
                finally:
                    db.close()

                logger.info(
                    f"Documento {document_id} removido do índice ({len(point_ids)} chunks)"
                )
                return True

            return False

        except Exception as e:
            logger.error(f"Erro ao deletar documento {document_id}: {e}")
            return False


# Instância global
vector_indexer = VectorIndexer(
    qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
    qdrant_api_key=os.getenv("QDRANT_API_KEY"),
)
