import streamlit as st
import sys
import os

# Adicionar o diretório ui ao path para importar os módulos
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from api_client import check_api_health, search_documents
from styles import configure_page, render_header
from session_manager import SessionManager

# Configuração da página
configure_page("Busca Semântica", "🔍")


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

    st.header("🔍 Busca Semântica")
    st.write("Encontre informações específicas nos seus documentos.")

    search_query = st.text_input(
        "O que você está procurando?",
        placeholder="Ex: contratos de 2023, valores acima de 10000, documentos de pessoa física",
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        limit = st.slider("Número de resultados:", 1, 10, 5)

    if st.button("🔍 Buscar", type="primary") and search_query:
        with st.spinner("Buscando..."):
            session_id = SessionManager.get_session_id()
            results = search_documents(search_query, session_id, limit)

            if results and results.get("results"):
                st.markdown(f"### 📋 {len(results['results'])} resultados encontrados")

                for i, result in enumerate(results["results"], 1):
                    with st.container():
                        st.markdown(
                            f"**Resultado {i}** - Relevância: {result['score']:.2f}"
                        )
                        st.markdown(
                            f"**Documento:** {result.get('document_id', 'Sem ID')[:8]}..."
                        )
                        st.markdown(
                            f"**Conteúdo:** {result.get('chunk_text', 'Texto não disponível')}"
                        )

                        # Mostrar informações adicionais se disponíveis
                        if result.get("chunk_index") is not None:
                            st.caption(f"Chunk #{result['chunk_index']}")

                        st.divider()
            else:
                st.info("Nenhum resultado encontrado.")


if __name__ == "__main__":
    main()
