FROM node:22-slim AS build
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web ./
ARG API_ORIGIN
ENV API_ORIGIN=$API_ORIGIN CREDITIQ_DEPLOYMENT=true NEXT_TELEMETRY_DISABLED=1
RUN npm run build && npm prune --omit=dev
FROM node:22-slim
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 CREDITIQ_DEPLOYMENT=true PORT=3000
COPY --from=build --chown=node:node /app ./
USER node
EXPOSE 3000
CMD ["sh", "-c", "exec node node_modules/next/dist/bin/next start --hostname 0.0.0.0 --port ${PORT:-3000}"]
