FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # UV_SYSTEM_PYTHON fuerza a uv a usar el python del sistema sin venv
    UV_SYSTEM_PYTHON=1 

WORKDIR /app

# === Dependencias del sistema ===
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    curl \
    # Dependencias para WeasyPrint y PDF
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz-icu0 \
    libharfbuzz0b \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    # Fuentes para WeasyPrint
    fonts-liberation \
    # Debugging
    gdb \
    procps \
    && rm -rf /var/lib/apt/lists/*

# === Instalación de UV y preparación de dependencias ===
COPY pyproject.toml ./
RUN curl -Ls https://astral.sh/uv/install.sh | bash && \
    cp /root/.local/bin/uv /usr/local/bin/uv && \
    # Generamos el requirements.txt
    uv pip compile pyproject.toml -o requirements.txt && \
    # Ajuste manual de limiter directamente en el archivo generado
    sed -i 's/fastapi-limiter>=.*/fastapi-limiter==0.1.6/' requirements.txt

# === Instalación limpia de Python ===
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    # Instalamos todo desde el requirements generado por uv + tus fixes específicos
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir \
    "fastapi-mail==1.5.0" \
    "fastapi-limiter==0.1.6" \
    "pydantic>=2.7.0" \
    "pydantic-settings>=2.0.3" \
    "fastapi-pagination>=0.12.9"

# === ✅ Verificación Integral ===
RUN python -c "import fastapi_limiter; print('✅ Limiter OK')" && \
    python -c "from fastapi_mail import ConnectionConfig; print('✅ Mail OK')" && \
    python -c "from pydantic import SecretStr; print('✅ Pydantic OK')" && \
    python -c "from weasyprint import HTML; print('✅ WeasyPrint OK')"

# === Copia el código (Al final para máxima velocidad de caché) ===
COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]