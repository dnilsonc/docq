import streamlit as st
from api_client import check_api_health, list_documents
from styles import configure_page, render_header
from session_manager import SessionManager

# Configuração da página com título elegante
st.set_page_config(
    page_title="DocQ - Navegação",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Aplicar CSS customizado
from styles import apply_custom_css

apply_custom_css()


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

    # Mensagem de boas-vindas
    st.markdown("## 🏠 Bem-vindo ao DocQ!")
    st.markdown(
        """
    Este é um sistema completo de OCR e Inteligência Artificial para processamento e consulta inteligente de documentos.
    
    ### 🚀 Funcionalidades Disponíveis:
    
    - **📤 Upload de Documentos**: Envie PDFs, imagens e outros documentos para processamento automático
    - **❓ Perguntas e Respostas**: Faça perguntas sobre seus documentos usando IA
    - **🔍 Busca Semântica**: Encontre informações específicas nos seus documentos
    - **📋 Gerenciar Documentos**: Visualize e gerencie todos os seus documentos
    
    ### 📊 Status do Sistema
    """
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        if check_api_health():
            st.success("✅ API Online")
        else:
            st.error("❌ API Offline")

    with col2:
        session_id = SessionManager.get_session_id()
        docs = list_documents(session_id)
        st.metric("📄 Documentos", len(docs) if docs else 0)

    with col3:
        processed_docs = [
            doc for doc in (docs or []) if doc.get("status") in ["completed", "indexed"]
        ]
        st.metric("✅ Processados", len(processed_docs))

    # Instruções
    st.markdown("### 🧭 Como começar:")
    st.markdown(
        """
    1. 📤 **Faça upload dos seus documentos** na página de Upload
    2. ⏳ **Aguarde o processamento** (OCR e indexação)
    3. ❓ **Faça perguntas** ou 🔍 **realize buscas** nos documentos
    4. 📋 **Gerencie seus documentos** conforme necessário
    """
    )

    # Navegação
    st.markdown("### 🧭 Navegação:")
    st.info(
        "Use o menu lateral para navegar entre as diferentes funcionalidades do sistema."
    )

    # Características do sistema
    st.markdown("### 🌟 Características:")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
        **🔒 Segurança:**
        - Processamento local de documentos
        - Dados armazenados com segurança
        
        **⚡ Performance:**
        - OCR otimizado para velocidade
        - Busca semântica avançada
        """
        )

    with col2:
        st.markdown(
            """
        **🤖 Inteligência Artificial:**
        - Extração automática de metadados
        - Respostas contextuais precisas
        
        **📊 Suporte a formatos:**
        - PDF, PNG, JPEG, TIFF
        - Processamento em lote
        """
        )


if __name__ == "__main__":
    main()
