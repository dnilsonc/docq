import streamlit as st
import sys
import os

# Adicionar o diretório ui ao path para importar os módulos
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from api_client import check_api_health, list_documents, ask_question
from styles import configure_page, render_header
from session_manager import SessionManager

# Configuração da página
configure_page("Perguntas e Respostas", "❓")


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

    st.header("❓ Perguntas e Respostas")
    st.write("Faça perguntas sobre seus documentos usando IA.")

    # Listar documentos disponíveis
    session_id = SessionManager.get_session_id()
    docs = list_documents(session_id)
    if not docs or not isinstance(docs, list):
        st.warning("Nenhum documento disponível. Faça upload primeiro!")
        return

    # Verificar se os documentos têm a estrutura esperada
    valid_docs = []
    for doc in docs:
        if isinstance(doc, dict) and "filename" in doc and "id" in doc:
            valid_docs.append(doc)

    if not valid_docs:
        st.warning("Nenhum documento válido encontrado. Verifique a API!")
        return

    # Criar mapeamento de seleção para IDs
    doc_options = ["Todos os documentos"]
    doc_id_map = {"Todos os documentos": None}

    for doc in valid_docs:
        doc_display = f"{doc.get('filename', 'Sem nome')} (ID: {str(doc.get('id', 'N/A'))[:8]}...)"
        doc_options.append(doc_display)
        doc_id_map[doc_display] = doc.get("id")

    # Seleção de documento (opcional)
    selected_doc = st.selectbox("Documento específico (opcional):", doc_options)

    # Campo de pergunta
    question = st.text_area(
        "Sua pergunta:",
        placeholder="Ex: Qual é o valor total do contrato? Quem são as partes envolvidas?",
        height=100,
    )

    if st.button("🤖 Perguntar", type="primary") and question:
        # Extrair ID do documento usando o mapeamento
        doc_id = doc_id_map.get(selected_doc)

        with st.spinner("Processando pergunta..."):
            result = ask_question(question, session_id, doc_id)

            if result:
                st.markdown("### 🎯 Resposta")
                st.markdown(f"{result['answer']}")

                if result.get("sources"):
                    st.markdown("### 📚 Fontes")
                    for i, source in enumerate(result["sources"], 1):
                        with st.expander(
                            f"Fonte {i} - Doc {source.get('document_id', 'N/A')[:8]}..."
                        ):
                            st.write(
                                f"**Trecho relevante:** {source.get('chunk_text', 'Texto não disponível')}"
                            )
                            st.write(
                                f"**Confiança:** {source.get('relevance_score', 0.0):.2f}"
                            )


if __name__ == "__main__":
    main()
