FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services /app/services
COPY config /app/config

ENV PYTHONPATH=/app

CMD ["python", "-m", "services.edge_ingest.main"]
