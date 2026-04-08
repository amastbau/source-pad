FROM python:3.13-slim

WORKDIR /app

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ src/
COPY static/ static/

# Install dependencies
RUN uv sync --no-dev

# Data volume for ChromaDB persistence
VOLUME /app/data

ENV CHROMA_PATH=/app/data/chroma
ENV HOST=0.0.0.0
ENV PORT=8090

EXPOSE 8090

CMD ["uv", "run", "source-pad", "serve"]
