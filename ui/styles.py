import streamlit as st
from typing import Dict

# CSS customizado
CUSTOM_CSS = """
<style>
    .main-header {
        text-align: center;
        padding: 2rem 0;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    
    .metric-card {
        background: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #667eea;
        margin: 1rem 0;
    }
    
    .status-processing {
        color: #ff9800;
        font-weight: bold;
    }
    
    .status-completed {
        color: #4caf50;
        font-weight: bold;
    }
    
    .status-error {
        color: #f44336;
        font-weight: bold;
    }
    
    .metadata-section {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
</style>
"""


def apply_custom_css():
    """Aplica o CSS customizado à página"""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def render_header():
    """Renderiza o cabeçalho principal"""
    st.markdown(
        """
    <div class="main-header">
        <h1>📄 DocQ - Sistema de OCR e IA</h1>
        <p>Upload, processamento e consulta inteligente de documentos</p>
    </div>
    """,
        unsafe_allow_html=True,
    )


def render_metadata(metadata: Dict):
    """Renderiza metadados extraídos"""
    if not metadata:
        return

    st.markdown("### 📊 Metadados Extraídos")

    col1, col2 = st.columns(2)

    with col1:
        if metadata.get("cnpj"):
            st.info(f"**CNPJ:** {metadata['cnpj']}")
        if metadata.get("cpf"):
            st.info(f"**CPF:** {metadata['cpf']}")
        if metadata.get("emails"):
            st.info(f"**Emails:** {', '.join(metadata['emails'])}")

    with col2:
        if metadata.get("dates"):
            st.info(f"**Datas:** {', '.join(metadata['dates'])}")
        if metadata.get("values"):
            st.info(f"**Valores:** {', '.join(metadata['values'])}")
        if metadata.get("phones"):
            st.info(f"**Telefones:** {', '.join(metadata['phones'])}")


def configure_page(page_title: str, page_icon: str = "📄"):
    """Configura a página do Streamlit"""
    st.set_page_config(
        page_title=f"DocQ - {page_title}",
        page_icon=page_icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_custom_css()
