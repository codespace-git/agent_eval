# Use Python 3.13.5 slim image
FROM python:3.13.5-slim

# Environment settings
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install Python dependencies

RUN pip install --upgrade pip && pip install flask

# Copy the rest of the app
COPY . .

# Expose Flask port
EXPOSE 5000

# Healthcheck (hit / route)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl --fail http://localhost:5000/ || exit 1

# Start the app
CMD ["python", "serp_api.py"]

