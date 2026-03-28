FROM python:3.9-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Runtime libs for tflite-runtime / numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
    libstdc++6 \
    libgomp1 \
    libffi8 \
  && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip setuptools wheel

# Dependencies (cached unless requirements.txt changes)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy project folders
COPY src/ /app/src/
COPY www/ /app/www/
COPY inference/ /app/inference/
COPY tests/ /app/tests/

CMD ["python", "/app/src/main.py"]
