# Use a lightweight, stable Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install dependencies first to maximize Docker cache reuse across code edits
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy project files
COPY pyproject.toml .
# OpenEnv /web reads /app/README.md first, so map web docs there explicitly.
COPY WEB_README.md ./README.md
COPY openenv.yaml .
COPY models.py .
COPY env.py .
COPY __init__.py .
COPY client.py .
COPY server ./server

# Install local package metadata/entrypoints without reinstalling dependencies
RUN pip install --no-deps .

# Expose the standard OpenEnv port
EXPOSE 8000

# Start the FastAPI/OpenEnv app directly (openenv serve is not implemented in v0.2.3)
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
