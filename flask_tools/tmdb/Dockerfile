# Use Python 3.13.5 slim base image
FROM python:3.13.5-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy only requirements first for better caching
RUN pip install --upgrade pip && pip install flask

# Copy application files and data
COPY . .

# Expose the port your Flask app runs on
EXPOSE 5002

# Add a healthcheck hitting the root route
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl --fail http://localhost:5002/ || exit 1

# Run the app
CMD ["python", "tmdb_api.py"]

