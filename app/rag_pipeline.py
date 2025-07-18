import os
from typing import List, Dict, Optional, Any
import json

from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain.schema import Document as LangchainDocument
from langchain.llms.base import LLM
from langchain.callbacks.manager import CallbackManagerForLLMRun

try:
    from groq import Groq

    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from loguru import logger
from vectordb.indexer import vector_indexer
from datetime import datetime
from db.session import get_db
from db.models import Document


class SimpleGroqLLM(LLM):
    """Wrapper simples para o Groq API"""

    client: Any = None
    model_name: str = "llama3-70b-8192"

    def __init__(self, api_key: str, model_name: str = "llama3-70b-8192"):
        super().__init__()
        if not GROQ_AVAILABLE:
            raise ImportError("Biblioteca groq não instalada")

        self.client = Groq(api_key=api_key)
        self.model_name = model_name

    @property
    def _llm_type(self) -> str:
        return "groq"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.3,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Erro na chamada Groq: {e}")
            return "Desculpe, ocorreu um erro ao processar sua pergunta."


class SimpleOpenAILLM(LLM):
    """Wrapper simples para OpenAI API"""

    client: Any = None
    model_name: str = "gpt-3.5-turbo"

    def __init__(self, api_key: str, model_name: str = "gpt-3.5-turbo"):
        super().__init__()
        if not OPENAI_AVAILABLE:
            raise ImportError("Biblioteca openai não instalada")

        self.client = OpenAI(api_key=api_key)
        self.model_name = model_name

    @property
    def _llm_type(self) -> str:
        return "openai"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.3,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Erro na chamada OpenAI: {e}")
            return "Desculpe, ocorreu um erro ao processar sua pergunta."


class FallbackLLM(LLM):
    """LLM de fallback que usa templates simples"""

    @property
    def _llm_type(self) -> str:
        return "fallback"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:

        # Extrair contexto e pergunta do prompt
        if "Contexto:" in prompt and "Pergunta:" in prompt:
            try:
                context_part = (
                    prompt.split("Contexto:")[1].split("Pergunta:")[0].strip()
                )
                question_part = (
                    prompt.split("Pergunta:")[1].split("Resposta:")[0].strip()
                )

                # Buscar palavras-chave da pergunta no contexto
                question_words = set(question_part.lower().split())
                context_words = context_part.lower().split()

                # Encontrar sentenças relevantes
                sentences = context_part.split(".")
                relevant_sentences = []

                for sentence in sentences:
                    sentence_words = set(sentence.lower().split())
                    if question_words.intersection(sentence_words):
                        relevant_sentences.append(sentence.strip())

                if relevant_sentences:
                    return (
                        f"Com base nos documentos: {' '.join(relevant_sentences[:2])}"
                    )
                else:
                    return "Não encontrei informações específicas para responder essa pergunta nos documentos fornecidos."

            except Exception as e:
                logger.error(f"Erro no LLM fallback: {e}")

        return "Desculpe, não consegui processar sua pergunta adequadamente."


class RAGPipeline:
    """Pipeline completo de RAG (Retrieval-Augmented Generation)"""

    def __init__(self):
        self.llm = self._initialize_llm()

        # Template para prompts em português
        self.prompt_template = PromptTemplate(
            input_variables=["context", "question"],
            template="""
            Você é um assistente especializado em responder perguntas sobre documentos.

            Contexto dos documentos:
            {context}

            Pergunta: {question}

            Instruções:
            - Seja preciso e objetivo
            - Cite trechos relevantes quando possível
            - Responda em português

            Resposta:""",
        )

        logger.info(f"RAG Pipeline inicializado com LLM: {self.llm._llm_type}")

    def _initialize_llm(self) -> LLM:
        """Inicializar LLM com fallback"""

        # Tentar Groq primeiro
        groq_api_key = os.getenv("GROQ_API_KEY")
        if groq_api_key and GROQ_AVAILABLE:
            try:
                return SimpleGroqLLM(api_key=groq_api_key)
            except Exception as e:
                logger.warning(f"Erro ao inicializar Groq: {e}")

        # Tentar OpenAI
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if openai_api_key and OPENAI_AVAILABLE:
            try:
                return SimpleOpenAILLM(api_key=openai_api_key)
            except Exception as e:
                logger.warning(f"Erro ao inicializar OpenAI: {e}")

        # Usar fallback
        logger.warning("Usando LLM de fallback (sem API externa)")
        return FallbackLLM()

    def retrieve_context(
        self,
        query: str,
        max_chunks: int = 3,
        document_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> List[Dict]:
        """Recuperar contexto relevante usando busca vetorial"""

        try:
            # Se session_id for fornecido, obter IDs dos documentos válidos da sessão
            session_doc_ids = None
            if session_id and not document_id:
                db = next(get_db())
                try:
                    valid_docs = (
                        db.query(Document)
                        .filter(
                            Document.session_id == session_id,
                            Document.session_expires_at > datetime.utcnow(),
                            Document.is_active == True,
                            Document.status.in_(["indexed", "ready"]),
                        )
                        .all()
                    )
                    session_doc_ids = [str(doc.id) for doc in valid_docs]
                finally:
                    db.close()

            # Buscar chunks relevantes
            search_results = vector_indexer.search_similar(
                query=query,
                limit=max_chunks,
                score_threshold=0.3,  # Limiar mais baixo para mais resultados
                document_id=document_id,
                session_doc_ids=session_doc_ids,
            )

            if not search_results:
                doc_info = f" no documento {document_id}" if document_id else ""
                logger.warning(f"Nenhum contexto encontrado para: {query}{doc_info}")
                return []

            # Filtrar e formatar resultados
            context_chunks = []
            for result in search_results:
                context_chunks.append(
                    {
                        "text": result["chunk_text"],
                        "document_id": result["document_id"],
                        "score": result["score"],
                        "chunk_index": result["chunk_index"],
                    }
                )

            doc_info = f" no documento {document_id}" if document_id else ""
            logger.info(
                f"Recuperados {len(context_chunks)} chunks para contexto{doc_info}"
            )
            return context_chunks

        except Exception as e:
            logger.error(f"Erro ao recuperar contexto: {e}")
            return []

    def generate_answer(self, question: str, context_chunks: List[Dict]) -> Dict:
        """Gerar resposta usando LLM"""

        try:
            # Preparar contexto
            if not context_chunks:
                return {
                    "answer": "Desculpe, não encontrei informações relevantes nos documentos para responder sua pergunta.",
                    "sources": [],
                    "confidence": 0.0,
                }

            # Combinar textos dos chunks
            context_text = "\n\n".join(
                [
                    f"Documento {chunk['document_id'][:8]}: {chunk['text']}"
                    for chunk in context_chunks
                ]
            )

            # Criar prompt
            prompt = self.prompt_template.format(
                context=context_text, question=question
            )

            # Gerar resposta
            answer = self.llm(prompt)

            # Calcular confiança baseada nos scores dos chunks
            avg_score = sum(chunk["score"] for chunk in context_chunks) / len(
                context_chunks
            )
            confidence = min(avg_score, 1.0)

            # Preparar fontes
            sources = [
                {
                    "document_id": chunk["document_id"],
                    "chunk_text": (
                        chunk["text"][:200] + "..."
                        if len(chunk["text"]) > 200
                        else chunk["text"]
                    ),
                    "relevance_score": chunk["score"],
                }
                for chunk in context_chunks
            ]

            return {
                "answer": answer.strip(),
                "sources": sources,
                "confidence": confidence,
                "chunks_used": len(context_chunks),
            }

        except Exception as e:
            logger.error(f"Erro ao gerar resposta: {e}")
            return {
                "answer": "Desculpe, ocorreu um erro ao processar sua pergunta.",
                "sources": [],
                "confidence": 0.0,
            }

    def ask_question(
        self,
        question: str,
        max_chunks: int = 3,
        document_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict:
        """Pipeline completo: pergunta → recuperação → geração"""

        logger.info(f"Processando pergunta: {question}")
        if document_id:
            logger.info(f"Filtrando por documento: {document_id}")

        try:
            # 1. Recuperar contexto relevante
            context_chunks = self.retrieve_context(
                question, max_chunks, document_id, session_id
            )

            # 2. Gerar resposta
            result = self.generate_answer(question, context_chunks)

            # 3. Adicionar informações extras
            result.update(
                {
                    "question": question,
                    "timestamp": str(datetime.now()),
                    "method": "RAG",
                    "document_filter": document_id,
                }
            )

            logger.info(
                f"Pergunta processada com sucesso. Confiança: {result['confidence']:.2f}"
            )

            return result

        except Exception as e:
            logger.error(f"Erro no pipeline RAG: {e}")
            return {
                "answer": "Desculpe, ocorreu um erro interno ao processar sua pergunta.",
                "sources": [],
                "confidence": 0.0,
                "error": str(e),
            }


# Instância global
rag_pipeline = RAGPipeline()
