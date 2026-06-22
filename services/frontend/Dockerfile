FROM node:22-alpine AS deps

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts


FROM node:22-alpine AS builder

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build


FROM node:22-alpine AS runner

WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 bitmod && \
    adduser --system --uid 1001 bitmod

COPY --from=builder /app/public ./public
COPY --from=builder --chown=bitmod:bitmod /app/.next/standalone ./
COPY --from=builder --chown=bitmod:bitmod /app/.next/static ./.next/static

USER bitmod

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000/',r=>{process.exit(r.statusCode<400?0:1)}).on('error',()=>process.exit(1))"

CMD ["node", "server.js"]
