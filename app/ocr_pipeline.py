import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import time
import re
from datetime import datetime
import os

from paddleocr import PaddleOCR
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from PIL import Image
import torch

from loguru import logger
from db.models import Document
from db.session import SessionLocal


class OCRPipeline:
    """Pipeline completo de OCR com PaddleOCR e TrOCR"""

    def __init__(self):
        # Inicializar PaddleOCR
        self.paddle_ocr = PaddleOCR(
            use_angle_cls=True,
            lang="pt",
            use_gpu=torch.cuda.is_available(),
            show_log=False,
        )

        # Configuração de threshold de confiança
        self.confidence_threshold = float(os.getenv("OCR_CONFIDENCE_THRESHOLD", 0.3))
        logger.info(
            f"OCR configurado com threshold de confiança: {self.confidence_threshold}"
        )

        # Inicializar TrOCR (opcional para refinar texto)
        try:
            self.trocr_processor = TrOCRProcessor.from_pretrained(
                "microsoft/trocr-base-stage1"
            )
            self.trocr_model = VisionEncoderDecoderModel.from_pretrained(
                "microsoft/trocr-base-stage1"
            )
            self.trocr_available = True
            logger.info("TrOCR carregado com sucesso")
        except Exception as e:
            logger.warning(f"TrOCR não disponível: {e}")
            self.trocr_available = False

        # Padrões regex para extração de campos
        self.patterns = {
            "cnpj": re.compile(r"\d{2}\.?\d{3}\.?\d{3}\/?\d{4}-?\d{2}"),
            "cpf": re.compile(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}"),
            "data": re.compile(r"\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}"),
            "valor": re.compile(r"R\$?\s*\d{1,3}(?:\.\d{3})*(?:,\d{2})?"),
            "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
            "telefone": re.compile(r"\(?\d{2}\)?\s*\d{4,5}-?\d{4}"),
        }

    def preprocess_image(self, image_path: str) -> np.ndarray:
        """Pré-processamento da imagem para melhorar OCR"""

        # Carregar imagem
        image = cv2.imread(image_path)

        if image is None:
            raise ValueError(f"Não foi possível carregar a imagem: {image_path}")

        # Converter para escala de cinza
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Aplicar filtro gaussiano para suavizar
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        # Binarização adaptativa
        binary = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )

        # Operações morfológicas para limpar ruído
        kernel = np.ones((2, 2), np.uint8)
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        return cleaned

    def extract_text_paddleocr(self, image_path: str) -> Tuple[str, List[Dict]]:
        """Extrair texto usando PaddleOCR"""

        try:
            # Executar OCR
            result = self.paddle_ocr.ocr(image_path, cls=True)

            if not result or not result[0]:
                logger.warning(f"Nenhum texto encontrado em {image_path}")
                return "", []

            # Extrair texto e informações
            text_blocks = []
            full_text = []
            discarded_count = 0

            for line in result[0]:
                bbox, (text, confidence) = line

                # Filtrar resultados com baixa confiança (agora configurável)
                if confidence > self.confidence_threshold:
                    full_text.append(text)
                    text_blocks.append(
                        {"text": text, "confidence": confidence, "bbox": bbox}
                    )
                else:
                    discarded_count += 1

            # Juntar todo o texto
            extracted_text = " ".join(full_text)

            logger.info(
                f"OCR extraiu {len(text_blocks)} blocos de texto de {image_path}"
            )
            if discarded_count > 0:
                logger.info(
                    f"Descartados {discarded_count} blocos com confiança < {self.confidence_threshold}"
                )

            return extracted_text, text_blocks

        except Exception as e:
            logger.error(f"Erro no OCR PaddleOCR: {e}")
            return "", []

    def refine_with_trocr(self, image_path: str, text_blocks: List[Dict]) -> str:
        """Refinar texto usando TrOCR (opcional)"""

        if not self.trocr_available:
            return ""

        try:
            # Carregar imagem
            image = Image.open(image_path).convert("RGB")

            # Processar imagem completa com TrOCR
            pixel_values = self.trocr_processor(
                images=image, return_tensors="pt"
            ).pixel_values
            generated_ids = self.trocr_model.generate(pixel_values)
            refined_text = self.trocr_processor.batch_decode(
                generated_ids, skip_special_tokens=True
            )[0]

            logger.info("Texto refinado com TrOCR")
            return refined_text

        except Exception as e:
            logger.warning(f"Erro no TrOCR: {e}")
            return ""

    def extract_metadata(self, text: str) -> Dict:
        """Extrair metadados estruturados do texto usando regex"""

        metadata = {}

        # Extrair campos usando padrões regex
        for field_name, pattern in self.patterns.items():
            matches = pattern.findall(text.upper())
            if matches:
                metadata[field_name] = list(set(matches))  # Remover duplicatas

        # Limpeza e formatação específica
        if "valor" in metadata:
            # Limpar valores monetários
            clean_values = []
            for valor in metadata["valor"]:
                # Remover caracteres extras e normalizar
                clean_value = re.sub(r"[^\d,.]", "", valor)
                if clean_value:
                    clean_values.append(clean_value)
            metadata["valor"] = clean_values

        # Estatísticas do texto
        metadata["stats"] = {
            "total_chars": len(text),
            "total_words": len(text.split()),
            "total_lines": len(text.split("\n")),
        }

        logger.info(f"Metadados extraídos: {list(metadata.keys())}")

        return metadata

    def process_document(self, document_id: str, file_path: str) -> Dict:
        """Processar documento completo"""

        start_time = time.time()

        try:
            logger.info(f"Iniciando processamento OCR para documento {document_id}")

            # 1. Pré-processamento da imagem (ativado)
            use_preprocessing = (
                os.getenv("OCR_USE_PREPROCESSING", "true").lower() == "true"
            )
            if use_preprocessing:
                try:
                    preprocessed_image = self.preprocess_image(file_path)
                    logger.info("Pré-processamento de imagem aplicado")
                except Exception as e:
                    logger.warning(
                        f"Erro no pré-processamento: {e}, usando imagem original"
                    )

            # 2. Extração de texto principal com PaddleOCR
            extracted_text, text_blocks = self.extract_text_paddleocr(file_path)

            # 3. Refinamento opcional com TrOCR
            refined_text = ""
            if self.trocr_available and extracted_text:
                refined_text = self.refine_with_trocr(file_path, text_blocks)

            # 4. Usar o melhor texto disponível
            final_text = (
                refined_text
                if refined_text and len(refined_text) > len(extracted_text)
                else extracted_text
            )

            # 5. Extrair metadados
            metadata = self.extract_metadata(final_text)

            # 6. Calcular confiança média
            if text_blocks:
                avg_confidence = sum(
                    block["confidence"] for block in text_blocks
                ) / len(text_blocks)
            else:
                avg_confidence = 0.0

            processing_time = int(time.time() - start_time)

            # 7. Atualizar documento no banco
            db = SessionLocal()
            try:
                document = db.query(Document).filter(Document.id == document_id).first()
                if document:
                    document.extracted_text = final_text
                    document.document_metadata = metadata
                    document.ocr_confidence = {
                        "avg_confidence": avg_confidence,
                        "blocks_count": len(text_blocks),
                        "method": "PaddleOCR + TrOCR" if refined_text else "PaddleOCR",
                    }
                    document.processing_time = processing_time
                    document.processed_at = datetime.utcnow()
                    document.status = "processed"

                    db.commit()
                    logger.info(f"Documento {document_id} processado com sucesso")

            finally:
                db.close()

            return {
                "text": final_text,
                "metadata": metadata,
                "confidence": avg_confidence,
                "processing_time": processing_time,
                "blocks_count": len(text_blocks),
            }

        except Exception as e:
            logger.error(f"Erro no processamento OCR do documento {document_id}: {e}")

            # Marcar documento como erro no banco
            db = SessionLocal()
            try:
                document = db.query(Document).filter(Document.id == document_id).first()
                if document:
                    document.status = "error"
                    document.document_metadata = {"error": str(e)}
                    db.commit()
            finally:
                db.close()

            raise


# Instância global
ocr_pipeline = OCRPipeline()
