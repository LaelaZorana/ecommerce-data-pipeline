# CommercePipeline -- single image that runs the pipeline and serves the dashboard.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy the project.
COPY pipeline ./pipeline
COPY dashboard ./dashboard
COPY pyproject.toml README.md ./

# Build the warehouse at image-build time so the container starts with data ready.
# (Re-runnable at container start via the entrypoint below.)
RUN python -m pipeline run

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8501/_stcore/health').read()==b'ok' else 1)"

# Rebuild marts on start (cheap, ~1s) then serve the dashboard.
CMD ["sh", "-c", "python -m pipeline run && streamlit run dashboard/app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true"]
