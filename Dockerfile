FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

# === 1. Dependencias del sistema (Capa estable) ===
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential libpq-dev gcc curl \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-icu0 libharfbuzz0b \
    libcairo2 libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info \
    fonts-liberation gdb procps && \
    rm -rf /var/lib/apt/lists/*

# === 2. Instalación de UV ===
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvbin/uv
ENV PATH="/uvbin:${PATH}"

# === 3. Instalación de dependencias (Capa de caché) ===
# Copiamos solo los archivos de definición de dependencias primero
COPY pyproject.toml ./
# Si tienes uv.lock, inclúyelo también: COPY pyproject.toml uv.lock ./

# Instalamos directamente con uv (mucho más rápido que pip)
# Nota: Si necesitas fijar versiones específicas, hazlo en el pyproject.toml
RUN uv pip install .

# === 4. ✅ Verificación Integral ===
RUN python -c "import pydantic; print('✅ Pydantic OK')" && \
    python -c "import weasyprint; print('✅ WeasyPrint OK')"

# === 5. Copia del código ===
# Se hace al final para que cambios en el código no invaliden la caché de las librerías
COPY . .

EXPOSE 8000

# Usamos el comando que ya tienes definido para el desarrollo
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]