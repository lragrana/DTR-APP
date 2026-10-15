# ---- build the React app ----
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ARG VITE_TURNSTILE_SITEKEY
ENV VITE_TURNSTILE_SITEKEY=$VITE_TURNSTILE_SITEKEY
RUN npm run build

# ---- serve it with nginx (non-root, HTTPS only) ----
FROM nginxinc/nginx-unprivileged:stable-alpine
USER root
RUN apk upgrade --no-cache && apk add --no-cache openssl
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --chmod=755 nginx/10-self-signed-cert.sh /docker-entrypoint.d/10-self-signed-cert.sh
COPY --from=build /app/dist /usr/share/nginx/html
USER 101
EXPOSE 8080 8443
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD wget -q --spider --no-check-certificate https://127.0.0.1:8443/ || exit 1
