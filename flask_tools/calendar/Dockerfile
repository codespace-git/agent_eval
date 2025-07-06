# Use a lightweight official Python image
FROM python:3.13.5-slim

# Environment setup
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy files

# Install dependencies
RUN apt-get update && apt-get install -y curl && rm -rf /vars/lib/apt/lists/*
RUN pip install --upgrade pip
RUN pip install flask

COPY . .
# Expose the Flask port
EXPOSE 5003

HEALTHCHECK --interval=30s --timeout=5s --retries=3\
    CMD curl --fail http://localhost:5003/ || exit 1
# Start the Flask app
CMD ["python", "calendar.py"]
