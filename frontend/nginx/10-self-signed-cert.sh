#!/bin/sh
# Local/demo only: create a self-signed certificate at startup if none is mounted.
# In production, mount a real certificate (e.g. Let's Encrypt) at /etc/nginx/certs.
set -e
if [ -f /etc/nginx/certs/cert.pem ] && [ -f /etc/nginx/certs/key.pem ]; then
  mkdir -p /tmp/tls && cp /etc/nginx/certs/cert.pem /etc/nginx/certs/key.pem /tmp/tls/
  exit 0
fi
mkdir -p /tmp/tls
openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout /tmp/tls/key.pem -out /tmp/tls/cert.pem \
  -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" >/dev/null 2>&1
chmod 600 /tmp/tls/key.pem
echo "self-signed TLS certificate created"
