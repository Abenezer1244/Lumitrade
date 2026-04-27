FROM node:20-alpine AS builder
WORKDIR /app

COPY package.json package-lock.json ./
# eslint-config-next@16 declares a peer-dep on eslint@^9 while the project
# pins eslint@^8. Without --legacy-peer-deps, npm ci aborts on ERESOLVE
# and the dashboard service has been failing to build since 2026-04-26.
RUN npm ci --legacy-peer-deps

# Force fresh copy of source files
ARG CACHE_DATE=20260330b
COPY . .

ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
# SECURITY: Only NEXT_PUBLIC_* vars allowed as build args.
# NEVER pass SUPABASE_SERVICE_KEY or other server secrets as ARG — they burn into image layers.

ENV NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL
ENV NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY

RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
