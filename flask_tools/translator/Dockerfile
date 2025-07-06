# Use Python 3.13.5 slim base image
FROM python:3.13.5-slim

# Environment variables to keep container clean and predictable
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install curl for healthcheck and clean up
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install dependencies first for better Docker cache

RUN pip install --upgrade pip && pip install flask && pip install deep-translator

# Copy your app code
COPY . .

# Expose port used by Flask
EXPOSE 5006

# Healthcheck for Docker
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl --fail http://localhost:5006/ || exit 1

# Run your Flask app
CMD ["python", "translate.py"]
