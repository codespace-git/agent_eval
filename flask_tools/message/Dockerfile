# Use official lightweight Python 3.13.5 image
FROM python:3.13.5-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install Python dependencies

RUN pip install --upgrade pip 
RUN pip install flask

# Copy application code
COPY . .

# Expose port
EXPOSE 5005

# Healthcheck for the root health endpoint
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl --fail http://localhost:5005/ || exit 1

# Start the Flask app
CMD ["python", "message_server.py"]
