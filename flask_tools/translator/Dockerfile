
FROM python:3.13.5-slim


ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1


WORKDIR /app


RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*




COPY requirements.txt .


RUN pip install --upgrade pip && pip install -r requirements.txt


COPY . .


EXPOSE 5006


HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl --fail http://localhost:5006/ || exit 1


CMD ["python", "translate.py"]
