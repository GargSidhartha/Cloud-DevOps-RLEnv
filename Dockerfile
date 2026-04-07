# Use a lightweight, stable Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY openenv.yaml .
COPY models.py .
COPY env.py .
COPY __init__.py .
COPY client.py .
COPY server ./server

# Install dependencies (no-cache to save space)
RUN pip install --no-cache-dir .

# Expose the standard OpenEnv port
EXPOSE 8000

# Start the FastAPI/OpenEnv app directly (openenv serve is not implemented in v0.2.3)
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
