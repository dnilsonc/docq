import requests
import os
from typing import Dict, List, Optional

# Configuração da API
API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000")


def check_api_health() -> bool:
    """Verifica se a API está funcionando"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False


def upload_document(file, session_id: str, session_expires_at: str) -> Optional[Dict]:
    """Upload de documento para a API com informações de sessão"""
    try:
        files = {"file": (file.name, file.getvalue(), file.type)}
        data = {"session_id": session_id, "session_expires_at": session_expires_at}
        response = requests.post(f"{API_BASE_URL}/upload", files=files, data=data)

        if response.status_code == 200:
            return response.json()
        else:
            import streamlit as st

            st.error(f"Erro no upload: {response.text}")
            return None
    except Exception as e:
        import streamlit as st

        st.error(f"Erro ao conectar com a API: {str(e)}")
        return None


def get_document_status(doc_id: str) -> Optional[Dict]:
    """Obtém status de um documento"""
    try:
        response = requests.get(f"{API_BASE_URL}/document/{doc_id}")
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None


def list_documents(session_id: str) -> List[Dict]:
    """Lista documentos da sessão atual"""
    try:
        params = {"session_id": session_id}
        response = requests.get(f"{API_BASE_URL}/documents", params=params)
        if response.status_code == 200:
            result = response.json()
            # A API retorna {"documents": [...], "total": x, ...}
            if isinstance(result, dict) and "documents" in result:
                documents = result["documents"]
                # Garantir que é uma lista válida
                if isinstance(documents, list):
                    return documents
            # Fallback para formato de lista direta
            elif isinstance(result, list):
                return result
            return []
        return []
    except Exception as e:
        import streamlit as st

        st.error(f"Erro ao listar documentos: {str(e)}")
        return []


def ask_question(
    question: str, session_id: str, doc_id: Optional[str] = None
) -> Optional[Dict]:
    """Faz pergunta sobre os documentos da sessão"""
    try:
        payload = {"question": question, "session_id": session_id}
        if doc_id:
            payload["document_id"] = doc_id

        response = requests.post(
            f"{API_BASE_URL}/ask",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 200:
            return response.json()
        else:
            import streamlit as st

            st.error(f"Erro na pergunta: {response.text}")
            return None
    except Exception as e:
        import streamlit as st

        st.error(f"Erro ao conectar com a API: {str(e)}")
        return None


def search_documents(query: str, session_id: str, limit: int = 5) -> Optional[Dict]:
    """Busca semântica nos documentos da sessão"""
    try:
        payload = {"query": query, "session_id": session_id, "limit": limit}
        response = requests.post(
            f"{API_BASE_URL}/search",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 200:
            return response.json()
        else:
            import streamlit as st

            st.error(f"Erro na busca: {response.text}")
            return None
    except Exception as e:
        import streamlit as st

        st.error(f"Erro ao conectar com a API: {str(e)}")
        return None


def delete_document(doc_id: str) -> bool:
    """Deleta um documento"""
    try:
        response = requests.delete(f"{API_BASE_URL}/document/{doc_id}")
        return response.status_code == 200
    except:
        return False


def cleanup_expired_sessions() -> Optional[Dict]:
    """Solicita limpeza de sessões expiradas"""
    try:
        response = requests.post(f"{API_BASE_URL}/cleanup")
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None
