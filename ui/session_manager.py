import streamlit as st
import uuid
from datetime import datetime, timedelta
import time


class SessionManager:
    """Gerenciador de sessões temporárias"""

    SESSION_DURATION = timedelta(hours=4)  # 4 horas

    @classmethod
    def get_session_id(cls) -> str:
        """Obtém ou cria um ID de sessão único para este navegador"""
        if "session_id" not in st.session_state:
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.session_created = datetime.now()

        return st.session_state.session_id

    @classmethod
    def get_session_expires_at(cls) -> datetime:
        """Calcula quando a sessão expira"""
        if "session_created" not in st.session_state:
            st.session_state.session_created = datetime.now()

        return st.session_state.session_created + cls.SESSION_DURATION

    @classmethod
    def is_session_expired(cls) -> bool:
        """Verifica se a sessão expirou"""
        if "session_created" not in st.session_state:
            return True

        return datetime.now() > cls.get_session_expires_at()

    @classmethod
    def get_time_remaining(cls) -> str:
        """Retorna o tempo restante da sessão formatado"""
        if cls.is_session_expired():
            return "Expirada"

        remaining = cls.get_session_expires_at() - datetime.now()
        hours = int(remaining.total_seconds() // 3600)
        minutes = int((remaining.total_seconds() % 3600) // 60)

        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

    @classmethod
    def get_progress_percent(cls) -> float:
        """Retorna a porcentagem de tempo decorrido (0-100)"""
        if cls.is_session_expired():
            return 100.0

        if "session_created" not in st.session_state:
            return 0.0

        elapsed = datetime.now() - st.session_state.session_created
        progress = (
            elapsed.total_seconds() / cls.SESSION_DURATION.total_seconds()
        ) * 100
        return min(100.0, max(0.0, progress))

    @classmethod
    def reset_session(cls):
        """Reinicia a sessão criando um novo ID"""
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.session_created = datetime.now()
        st.rerun()

    @classmethod
    def render_session_info(cls):
        """Renderiza informações da sessão na sidebar"""
        with st.sidebar:
            st.markdown("---")
            st.markdown("### 🕒 Sessão Temporária")

            if cls.is_session_expired():
                st.error("⚠️ Sessão expirada!")
                if st.button("🔄 Nova Sessão"):
                    cls.reset_session()
            else:
                time_remaining = cls.get_time_remaining()
                progress = cls.get_progress_percent()

                st.write(f"**Tempo restante:** {time_remaining}")

                # Barra de progresso colorida
                if progress < 25:
                    color = "green"
                elif progress < 50:
                    color = "blue"
                elif progress < 75:
                    color = "orange"
                else:
                    color = "red"

                # Usar HTML personalizado para barra colorida
                st.markdown(
                    f"""
                    <div style="
                        background-color: #f0f2f6;
                        border-radius: 10px;
                        padding: 2px;
                        margin: 5px 0;
                    ">
                        <div style="
                            background-color: {color};
                            height: 15px;
                            border-radius: 8px;
                            width: {progress}%;
                            transition: width 0.3s ease;
                        "></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                st.caption(f"Sessão ID: `{cls.get_session_id()[:8]}...`")

                if st.button("🔄 Reiniciar Sessão"):
                    cls.reset_session()

            st.markdown(
                """
            <div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-top: 10px;">
                <small>
                <strong>ℹ️ Sobre as sessões:</strong><br>
                • Duração: 4 horas<br>
                • Documentos são automaticamente removidos após a expiração<br>
                • Cada aba do navegador = sessão única<br>
                • Sem necessidade de login
                </small>
            </div>
            """,
                unsafe_allow_html=True,
            )
