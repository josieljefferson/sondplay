# Imagem base leve
FROM python:3.11-slim

# Evita prompts interativos
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Instalar yt-dlp e outras dependências Python
RUN pip install --no-cache-dir yt-dlp

# Criar diretório da aplicação
WORKDIR /app

# Copiar requirements primeiro (para cache de dependências)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todos os arquivos da aplicação
COPY . .

# Criar diretório temporário para EPG
RUN mkdir -p tmp_epg

# Porta padrão
EXPOSE 8080

# Comando de execução
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "120", "app:app"]