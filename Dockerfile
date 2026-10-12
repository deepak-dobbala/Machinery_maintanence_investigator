FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends build-essential pkg-config libdbus-1-dev libglib2.0-dev && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV PORT=8080

CMD ["sh", "-c", "streamlit run app/ui.py --server.address 0.0.0.0 --server.port ${PORT} --server.headless true"]
