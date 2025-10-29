FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Delete webhook before start to avoid 409 error
CMD ["python3", "main.py"]