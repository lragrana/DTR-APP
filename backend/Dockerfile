FROM python:3.13-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Apply OS security updates and create an unprivileged user.
RUN apk upgrade --no-cache \
    && adduser -D -u 10001 appuser

WORKDIR /app
COPY requirements.txt .
# Install dependencies, then remove pip/setuptools: build tools are not needed at runtime.
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y pip setuptools

COPY --chown=appuser:appuser . .
USER appuser

EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/api/health', timeout=3).status == 200 else 1)"

# Production WSGI server instead of Flask's development server.
CMD ["gunicorn", "app:create_app()", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--access-logfile", "-"]
