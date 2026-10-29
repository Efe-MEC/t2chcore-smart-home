FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY python/requirements.txt /app/python/requirements.txt

RUN pip install --no-cache-dir \
    -r /app/python/requirements.txt

COPY python/ /app/python/

RUN mkdir -p /app/data

EXPOSE 8080

CMD ["uvicorn", "api.app:app", \
     "--app-dir", "/app/python", \
     "--host", "0.0.0.0", \
     "--port", "8080"]
