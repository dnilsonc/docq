import streamlit as st
import time
import sys
import os

# Adicionar o diretório ui ao path para importar os módulos
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from api_client import check_api_health, upload_document, get_document_status
from styles import configure_page, render_header, render_metadata
from session_manager import SessionManager

# Configuração da página
configure_page("Upload de Documentos", "📤")


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

    st.header("📤 Upload de Documentos")
    st.write(
        "Faça upload de PDFs ou imagens para processamento com OCR e extração de informações."
    )

    uploaded_file = st.file_uploader(
        "Escolha um arquivo",
        type=["pdf", "png", "jpg", "jpeg", "tiff"],
        help="Formatos suportados: PDF, PNG, JPEG, TIFF",
    )

    if uploaded_file is not None:
        col1, col2 = st.columns([2, 1])

        with col1:
            st.write(f"**Arquivo:** {uploaded_file.name}")
            st.write(f"**Tamanho:** {uploaded_file.size / 1024:.1f} KB")
            st.write(f"**Tipo:** {uploaded_file.type}")

        with col2:
            if st.button("🚀 Processar Documento", type="primary"):
                with st.spinner("Enviando documento..."):
                    session_id = SessionManager.get_session_id()
                    session_expires_at = (
                        SessionManager.get_session_expires_at().isoformat()
                    )
                    result = upload_document(
                        uploaded_file, session_id, session_expires_at
                    )

                    if result:
                        st.success("✅ Upload realizado com sucesso!")
                        doc_id = result.get("id")

                        if not doc_id:
                            st.error("❌ Erro: ID do documento não retornado pela API")
                            st.json(result)  # Mostrar resposta para debug
                            return

                        # Acompanhar processamento
                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        for i in range(100):
                            status = get_document_status(doc_id)
                            if status:
                                current_status = status["status"]
                                status_text.text(f"Status: {current_status}")

                                if current_status in ["completed", "indexed"]:
                                    progress_bar.progress(100)
                                    st.success("🎉 Processamento concluído!")

                                    # Mostrar resultados
                                    if status.get("extracted_text"):
                                        st.markdown("### 📄 Texto Extraído")
                                        with st.expander(
                                            "Ver texto completo", expanded=False
                                        ):
                                            st.text_area(
                                                "Texto",
                                                status.get("extracted_text", ""),
                                                height=200,
                                                disabled=True,
                                            )

                                    # Mostrar metadados
                                    if status.get("metadata"):
                                        render_metadata(status["metadata"])

                                    break
                                elif current_status == "error":
                                    st.error("❌ Erro no processamento")
                                    break
                                else:
                                    progress_bar.progress(i)

                            time.sleep(2)


if __name__ == "__main__":
    main()
