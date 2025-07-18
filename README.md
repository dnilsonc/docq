# 🔍 DocQ - OCR + RAG para Documentos

**DocQ** é uma solução completa de processamento de documentos que combina **OCR (Reconhecimento Óptico de Caracteres)**, **extração de informações** e **RAG (Retrieval-Augmented Generation)** para criar um sistema inteligente de perguntas e respostas sobre documentos escaneados.

## 🎯 Principais Funcionalidades

- ✅ **OCR Avançado**: PaddleOCR + TrOCR para extração precisa de texto
- ✅ **Extração de Metadados**: Identificação automática de CNPJ, datas, valores, emails
- ✅ **Busca Semântica**: Indexação vetorial com sentence-transformers e Qdrant
- ✅ **Sistema Q&A**: Perguntas e respostas inteligentes usando RAG
- ✅ **API RESTful**: FastAPI com documentação automática
- ✅ **Banco de Dados**: PostgreSQL para metadados e histórico
- ✅ **Deploy Containerizado**: Docker Compose para fácil implantação

## 🏗️ Arquitetura

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   Frontend  │───▶│   FastAPI    │───▶│ PostgreSQL  │
│ (Streamlit) │    │              │    │             │
└─────────────┘    └──────┬───────┘    └─────────────┘
                          │
                          ▼
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   Qdrant    │◀───│ OCR Pipeline │───▶│    LLM      │
│ (Vetores)   │    │ PaddleOCR +  │    │ (Groq/GPT)  │
│             │    │    TrOCR     │    │             │
└─────────────┘    └──────────────┘    └─────────────┘
```

## 🚀 Instalação e Configuração

### Pré-requisitos

- Docker e Docker Compose
- Python 3.10+ (para desenvolvimento local)
- 4GB RAM mínimo
- 2GB de espaço em disco

### 1. Clone o Repositório

```bash
git clone https://github.com/seu-usuario/docq.git
cd docq
```

### 2. Configuração das Variáveis de Ambiente

Crie um arquivo `.env` baseado no exemplo:

```bash
cp .env.example .env
```

Edite o `.env` com suas configurações:

```env
# Banco de dados
DATABASE_URL=postgresql://docq_user:docq_pass@localhost:5432/docq_db

# Qdrant
QDRANT_URL=http://localhost:6333

# LLM APIs (opcional - uma das duas)
GROQ_API_KEY=seu_groq_api_key_aqui
OPENAI_API_KEY=seu_openai_api_key_aqui

# Configurações
CHUNK_SIZE=300
CHUNK_OVERLAP=50
DEBUG=false
```

### 3. Deploy com Docker Compose

#### Opção A: Apenas Backend (Recomendado)

```bash
# Subir todos os serviços
docker-compose up -d

# Verificar se tudo está funcionando
docker-compose ps
```

#### Opção B: Com Interface Web

```bash
# Subir com interface Streamlit
docker-compose --profile ui up -d

# Verificar containers
docker-compose --profile ui ps
```

### 4. Verificação da Instalação

```bash
# Testar API
curl http://localhost:8000/health

# Acessar documentação da API
open http://localhost:8000/docs

# Acessar interface Streamlit (se usando --profile ui)
open http://localhost:8501
```

**Interface Streamlit disponível em:** `http://localhost:8501`

A interface web oferece:
- 📤 Upload intuitivo de documentos
- 📊 Visualização de metadados extraídos  
- ❓ Interface de perguntas e respostas
- 🔍 Busca semântica avançada
- 📋 Gerenciamento de documentos

## 📚 Como Usar

### 1. Upload de Documento

**Via cURL:**
```bash
curl -X POST "http://localhost:8000/upload" \
     -H "accept: application/json" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@seu_documento.pdf"
```

**Resposta:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "seu_documento.pdf",
  "status": "processing",
  "uploaded_at": "2024-01-15T10:30:00"
}
```

### 2. Verificar Status do Processamento

```bash
curl "http://localhost:8000/document/550e8400-e29b-41d4-a716-446655440000"
```

### 3. Fazer Perguntas sobre os Documentos

```bash
curl -X POST "http://localhost:8000/ask" \
     -H "Content-Type: application/json" \
     -d '{
       "question": "Qual o valor total da nota fiscal?",
       "max_chunks": 3
     }'
```

**Resposta:**
```json
{
  "answer": "Com base no documento, o valor total da nota fiscal é R$ 1.250,00.",
  "sources": [
    {
      "document_id": "550e8400-e29b-41d4-a716-446655440000",
      "chunk_text": "VALOR TOTAL: R$ 1.250,00",
      "relevance_score": 0.95
    }
  ],
  "confidence": 0.95,
  "question": "Qual o valor total da nota fiscal?",
  "timestamp": "2024-01-15T10:35:00"
}
```

### 4. Busca Textual

```bash
curl "http://localhost:8000/search?query=CNPJ&limit=5"
```

## 🛠️ Desenvolvimento Local

### 1. Configurar Ambiente Python

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

### 2. Configurar Banco de Dados

```bash
# Subir apenas PostgreSQL e Qdrant
docker-compose up postgres qdrant -d

# Configurar tabelas
python -c "from db.session import create_tables; create_tables()"
```

### 3. Executar API em Modo Debug

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Testes

```bash
# Instalar dependências de teste
pip install pytest pytest-asyncio httpx

# Executar testes
pytest tests/ -v
```

## 📊 Monitoramento

### Verificar Logs

```bash
# Logs da API
docker-compose logs -f api

# Logs do banco
docker-compose logs postgres

# Logs do Qdrant
docker-compose logs qdrant
```

### Métricas de Performance

```bash
# Status geral do sistema
curl http://localhost:8000/health

# Listar documentos processados
curl http://localhost:8000/documents?limit=10
```

## 🔧 Configurações Avançadas

### Ajustar Chunking

No arquivo `.env`:
```env
CHUNK_SIZE=500        # Tamanho dos chunks (caracteres)
CHUNK_OVERLAP=100     # Sobreposição entre chunks
```

### Configurar OCR

Para melhorar a extração de texto:
```env
OCR_CONFIDENCE_THRESHOLD=0.3    # Threshold de confiança (0.1-1.0)
OCR_USE_PREPROCESSING=true      # Pré-processamento de imagem
```

**Valores recomendados:**
- `0.1`: Aceita quase todo texto (pode incluir ruído)
- `0.3`: Padrão balanceado (recomendado)
- `0.5`: Mais restritivo (texto de alta qualidade)
- `0.7`: Muito restritivo (apenas texto muito claro)

### Configurar LLM

**Groq (Gratuito):**
```env
GROQ_API_KEY=gsk_...
```

**OpenAI:**
```env
OPENAI_API_KEY=sk-...
```

### Escalar Horizontalmente

```yaml
# docker-compose.yml
api:
  scale: 3  # Múltiplas instâncias da API
```

## 🚀 Deploy em Produção

### 1. Usando Docker Swarm

```bash
docker swarm init
docker stack deploy -c docker-compose.yml docq
```

### 2. Usando Kubernetes

```bash
# Gerar manifests
kompose convert -f docker-compose.yml

# Deploy
kubectl apply -f docq-*.yaml
```

### 3. Deploy em Nuvem

**Railway:**
```bash
railway login
railway link
railway up
```

**Render:**
- Conectar repositório GitHub
- Configurar variáveis de ambiente
- Deploy automático

## 📝 API Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/` | Health check básico |
| `GET` | `/health` | Status detalhado do sistema |
| `POST` | `/upload` | Upload de documento |
| `GET` | `/document/{id}` | Status do documento |
| `GET` | `/documents` | Listar documentos |
| `POST` | `/ask` | Fazer pergunta (RAG) |
| `GET` | `/search` | Busca textual |
| `DELETE` | `/document/{id}` | Deletar documento |

### Documentação Interativa

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🧪 Exemplos de Uso

### Processar Nota Fiscal

```python
import requests

# Upload
files = {'file': open('nota_fiscal.pdf', 'rb')}
response = requests.post('http://localhost:8000/upload', files=files)
doc_id = response.json()['id']

# Aguardar processamento
import time
while True:
    status = requests.get(f'http://localhost:8000/document/{doc_id}')
    if status.json()['status'] == 'indexed':
        break
    time.sleep(2)

# Fazer pergunta
question = {"question": "Qual o CNPJ do emissor?"}
answer = requests.post('http://localhost:8000/ask', json=question)
print(answer.json()['answer'])
```

### Extrair Metadados

```python
# Buscar documento processado
doc = requests.get(f'http://localhost:8000/document/{doc_id}')
metadata = doc.json()['metadata']

print(f"CNPJ: {metadata.get('cnpj', [])}")
print(f"Valores: {metadata.get('valor', [])}")
print(f"Datas: {metadata.get('data', [])}")
```

## 📈 Performance

### Benchmarks Típicos

- **Upload**: 2-5 segundos por documento
- **OCR**: 5-15 segundos por página
- **Indexação**: 1-3 segundos por documento
- **Busca**: < 100ms
- **Resposta RAG**: 1-5 segundos

### Otimizações

1. **GPU**: Habilitar CUDA para OCR mais rápido
2. **Cache**: Redis para cache de embeddings
3. **Workers**: Múltiplos workers Uvicorn
4. **Batch**: Processamento em lote

## ❗ Troubleshooting

### Problemas Comuns

**Erro de conexão com Qdrant:**
```bash
# Verificar se o serviço está rodando
docker-compose ps qdrant

# Verificar logs
docker-compose logs qdrant
```

**Erro de OCR:**
```bash
# Verificar dependências do sistema
docker exec -it docq_api apt list --installed | grep tesseract
```

**Erro de memória:**
```bash
# Aumentar memória Docker
# Docker Desktop > Settings > Resources > Memory
```

### Logs de Debug

```bash
# Habilitar debug
echo "DEBUG=true" >> .env
docker-compose restart api

# Ver logs detalhados
docker-compose logs -f api
```

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch: `git checkout -b feature/nova-funcionalidade`
3. Commit: `git commit -m 'Adiciona nova funcionalidade'`
4. Push: `git push origin feature/nova-funcionalidade`
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

## 🙏 Agradecimentos

- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) - OCR engine
- [TrOCR](https://huggingface.co/microsoft/trocr-base-stage1) - Transformer OCR
- [Qdrant](https://qdrant.tech/) - Vector database
- [LangChain](https://langchain.com/) - RAG framework
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework

---

**Desenvolvido com ❤️ para democratizar o acesso à informação em documentos** 