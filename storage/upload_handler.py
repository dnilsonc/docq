import os
import shutil
import uuid
from pathlib import Path
from typing import Optional
from fastapi import UploadFile, HTTPException
import magic
from loguru import logger

class FileUploadHandler:
    """Handler para upload e armazenamento de arquivos"""
    
    def __init__(self, upload_directory: str = "./data/uploads"):
        self.upload_directory = Path(upload_directory)
        self.upload_directory.mkdir(parents=True, exist_ok=True)
        
        # Tipos de arquivo permitidos
        self.allowed_types = {
            'application/pdf',
            'image/png', 
            'image/jpeg',
            'image/tiff'
        }
        
        # Tamanho máximo: 50MB
        self.max_file_size = 50 * 1024 * 1024
    
    def validate_file(self, file: UploadFile) -> bool:
        """Validar tipo e tamanho do arquivo"""
        
        # Verificar extensão
        allowed_extensions = {'.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif'}
        file_extension = Path(file.filename).suffix.lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Tipo de arquivo não permitido: {file_extension}"
            )
        
        # Verificar tamanho (aproximado)
        if hasattr(file.file, 'seek'):
            file.file.seek(0, 2)  # Ir para o final
            file_size = file.file.tell()
            file.file.seek(0)  # Voltar ao início
            
            if file_size > self.max_file_size:
                raise HTTPException(
                    status_code=400,
                    detail=f"Arquivo muito grande. Máximo: {self.max_file_size/1024/1024:.1f}MB"
                )
        
        return True
    
    def save_file(self, file: UploadFile, document_id: str) -> dict:
        """Salvar arquivo no disco e retornar informações"""
        
        try:
            # Validar arquivo
            self.validate_file(file)
            
            # Gerar nome único mantendo extensão original
            file_extension = Path(file.filename).suffix
            unique_filename = f"{document_id}{file_extension}"
            file_path = self.upload_directory / unique_filename
            
            # Salvar arquivo
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Obter informações do arquivo
            file_size = file_path.stat().st_size
            
            # Detectar MIME type real
            mime_type = magic.from_file(str(file_path), mime=True)
            
            # Validar MIME type
            if mime_type not in self.allowed_types:
                # Remover arquivo inválido
                file_path.unlink()
                raise HTTPException(
                    status_code=400,
                    detail=f"Tipo de arquivo não suportado: {mime_type}"
                )
            
            logger.info(f"Arquivo salvo: {file_path} ({file_size} bytes)")
            
            return {
                "file_path": str(file_path),
                "filename": file.filename,
                "size": file_size,
                "mime_type": mime_type
            }
            
        except Exception as e:
            logger.error(f"Erro ao salvar arquivo: {e}")
            raise HTTPException(status_code=500, detail=f"Erro ao salvar arquivo: {str(e)}")
    
    def delete_file(self, file_path: str) -> bool:
        """Remover arquivo do disco"""
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                logger.info(f"Arquivo removido: {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Erro ao remover arquivo {file_path}: {e}")
            return False

# Instância global
upload_handler = FileUploadHandler() 