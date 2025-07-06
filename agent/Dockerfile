# Use an official Python runtime as base
FROM python:3.13.5-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . .

# Expose Flask port (only if you're running Flask server; your agent script does not)
# EXPOSE 5000
# Run the script (adjust filename if needed)
CMD ["python", "agent.py"]
