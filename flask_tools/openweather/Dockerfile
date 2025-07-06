FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y curl && rm -rf /vars/lib/apt/list/*
RUN pip install --upgrade pip && pip install flask

COPY . .

EXPOSE 5001

HEALTHCHECK --interval=30s --timeout=5s --retries=3\
 CMD curl --fail http://localhost:5001/ || exit 1

CMD ["python","openweather_api.py"]
