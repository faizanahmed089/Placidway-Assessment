# Container image for Hugging Face Spaces (Docker SDK) or any Docker host.
FROM python:3.14-slim

# Hugging Face Spaces runs containers as user id 1000, so create that user and
# make sure everything the app writes to (data/, model cache) belongs to it.
RUN useradd --create-home --uid 1000 appuser
WORKDIR /home/appuser/app

# Where fastembed stores the embedding model. Set before the download below
# so the model is baked into the image and the app starts without downloading.
ENV FASTEMBED_CACHE_PATH=/home/appuser/model_cache \
    PYTHONUNBUFFERED=1

# Install dependencies first: this layer is cached until requirements change.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . .
RUN mkdir -p /home/appuser/model_cache && chown -R appuser:appuser /home/appuser
USER appuser

# At build time: download the embedding model and compute the chunk vectors,
# so the running container starts immediately.
RUN python -c "from app.knowledge_base import KnowledgeBase; KnowledgeBase.load()"

# Spaces expects the app on port 7860.
EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
