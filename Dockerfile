FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY app ./app

ENV PORT=8080

CMD ["sh", "-c", "streamlit run app/ui.py --server.address 0.0.0.0 --server.port ${PORT} --server.headless true"]
