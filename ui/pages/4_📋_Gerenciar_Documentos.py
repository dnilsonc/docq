import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os

# Adicionar o diretório ui ao path para importar os módulos
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from api_client import (
    check_api_health,
    list_documents,
    get_document_status,
    delete_document,
)
from styles import configure_page, render_header
from session_manager import SessionManager

# Configuração da página
configure_page("Gerenciar Documentos", "📋")


def main():
    # Verificar sessão
    if SessionManager.is_session_expired():
        st.error("⚠️ Sua sessão expirou! Clique em 'Nova Sessão' na barra lateral.")
        SessionManager.render_session_info()
        return

    # Renderizar informações da sessão na sidebar
    SessionManager.render_session_info()

    # Header principal
    render_header()

    # Verificação da API
    if not check_api_health():
        st.error("⚠️ API não está disponível. Verifique se os serviços estão rodando.")
        st.code("docker-compose up -d")
        return

    st.header("📋 Gerenciar Documentos")

    session_id = SessionManager.get_session_id()
    docs = list_documents(session_id)

    if not docs or not isinstance(docs, list):
        st.info("Nenhum documento encontrado.")
        return

    # Verificar se os documentos têm a estrutura esperada
    valid_docs = []
    for doc in docs:
        if isinstance(doc, dict) and all(
            key in doc for key in ["id", "filename", "status", "uploaded_at"]
        ):
            valid_docs.append(doc)

    if not valid_docs:
        st.warning("Nenhum documento válido encontrado. Verifique a API!")
        return

    st.write(f"**Total de documentos:** {len(valid_docs)}")

    # Tabela de documentos
    doc_data = []
    for doc in valid_docs:
        try:
            doc_data.append(
                {
                    "ID": str(doc.get("id", "N/A"))[:8] + "...",
                    "Nome": doc.get("filename", "Sem nome"),
                    "Status": doc.get("status", "Desconhecido"),
                    "Criado em": (
                        datetime.fromisoformat(
                            doc.get("uploaded_at", "2023-01-01T00:00:00").replace(
                                "Z", "+00:00"
                            )
                        ).strftime("%d/%m/%Y %H:%M")
                        if doc.get("uploaded_at")
                        else "N/A"
                    ),
                    "Chunks": doc.get("chunk_count", 0),
                }
            )
        except Exception as e:
            st.warning(f"Erro ao processar documento: {str(e)}")
            continue

    df = pd.DataFrame(doc_data)
    st.dataframe(df, use_container_width=True)

    # Ações em documentos
    st.markdown("### 🔧 Ações")

    try:
        selected_doc_id = st.selectbox(
            "Selecione um documento:",
            options=[doc.get("id", "N/A") for doc in valid_docs if doc.get("id")],
            format_func=lambda x: next(
                (
                    doc.get("filename", "Sem nome")
                    for doc in valid_docs
                    if doc.get("id") == x
                ),
                "Documento não encontrado",
            ),
        )
    except Exception as e:
        st.error(f"Erro ao carregar seleção de documentos: {str(e)}")
        selected_doc_id = None

    if selected_doc_id:
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("📊 Ver Detalhes"):
                status = get_document_status(selected_doc_id)
                if status:
                    st.json(status)

        with col2:
            if st.button("🔄 Atualizar Status"):
                st.rerun()

        with col3:
            if st.button("🗑️ Deletar", key="delete_btn", type="secondary"):
                st.session_state["confirm_delete"] = True

            if st.session_state.get("confirm_delete", False):
                if st.button(
                    "Confirmar exclusão", key="confirm_delete_btn", type="primary"
                ):
                    if delete_document(selected_doc_id):
                        st.success("Documento deletado!")
                        st.session_state["confirm_delete"] = False
                        st.rerun()
                    else:
                        st.error("Erro ao deletar documento")
                        st.session_state["confirm_delete"] = False
    else:
        st.warning("Nenhum documento válido selecionado.")


if __name__ == "__main__":
    main()
