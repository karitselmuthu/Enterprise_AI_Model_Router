FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt requirements-providers.txt ./
ARG INSTALL_PROVIDERS=false
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && if [ "$INSTALL_PROVIDERS" = "true" ]; then python -m pip install --no-cache-dir -r requirements-providers.txt; fi \
    && useradd --create-home --uid 10001 router
COPY app ./app
COPY configs ./configs
USER router
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/health/ready", timeout=2)'
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
