# ============================================================
# Muhai web image — the built SPA, served by nginx.
#
# nginx also reverse-proxies /api to the backend container, which is what
# makes the VPS deployment simple: browser, API and app all share one origin,
# so there is no CORS configuration and no VITE_API_URL to get wrong.
# ============================================================

FROM node:20-alpine AS builder

WORKDIR /app

# Copy the manifests first so a dependency install is only re-run when they
# change, not on every source edit.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Empty means "same origin" — nginx proxies /api to the backend. Override at
# build time only if the API lives on a different host:
#   docker compose build --build-arg VITE_API_URL=https://api.example.com web
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build


FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
