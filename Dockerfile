FROM python:3.11-slim

# Install tesseract for OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libtesseract-dev \
    libleptonica-dev \
    && rm -rf /var/lib/apt/lists/*

# Workdir
WORKDIR /app
COPY . /app

# Install pip dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose nothing (bot uses outgoing connections)
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
