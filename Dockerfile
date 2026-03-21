# Dockerfile
FROM python:3.12-slim

# === Configuración básica de Python ===
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# === Dependencias del sistema ===
RUN apt-get update && \
    apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    curl \
    gdb \
    procps \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz-icu0 \
    libharfbuzz0b \
    libcairo2 \
    libgdk-pixbuf-xlib-2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# === Instala Uv y dependencias de Python ===
COPY pyproject.toml ./
RUN curl -Ls https://astral.sh/uv/install.sh | bash && \
    cp /root/.local/bin/uv /usr/local/bin/uv && \
    uv pip compile pyproject.toml -o requirements.txt && \
    # Bajamos la versión de limiter para compatibilidad
    sed -i 's/fastapi-limiter>=.*/fastapi-limiter==0.1.6/' requirements.txt && \
    uv pip install -r requirements.txt --system

# === 🔧 FIX: Limpieza y reinstalación de librerías con conflictos de Pydantic v2 ===
RUN pip install --upgrade pip setuptools wheel && \
    pip uninstall -y fastapi-mail fastapi-limiter || true && \
    pip cache purge || true && \
    # Instalamos versiones probadas que funcionan con Pydantic 2.x
    pip install "fastapi-mail==1.5.0" "fastapi-limiter==0.1.6" "pydantic>=2.7.0" "pydantic-settings>=2.0.3"

# === ✅ Verificación Integral (Un solo paso para no ensuciar el build) ===
# IMPORTANTE: En 0.1.6 a veces el import es directo, en otras es desde .limiter
RUN python -c "import fastapi_limiter; print('✅ Limiter Base OK')" && \
    python -c "from fastapi_mail import ConnectionConfig; print('✅ Mail OK')" && \
    python -c "from pydantic import SecretStr; print('✅ Pydantic SecretStr OK')"

# === Copia el código del proyecto ===
COPY . .

# === Expone el puerto ===
EXPOSE 8000

# El comando se define en docker-compose, pero dejamos este como fallback
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]