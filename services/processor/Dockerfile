FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services/processor/runtime_processor.py /app/runtime_processor.py

CMD ["python", "runtime_processor.py"]
