# ===== Vue / Vite frontend =====
FROM node:22-alpine

WORKDIR /app

# 1) 依赖
COPY package.json package-lock.json ./
RUN npm ci

# 2) 源码
COPY index.html vite.config.js ./
COPY src/ ./src/

EXPOSE 5173

# Vite dev server — host: true 使容器外可访问
CMD ["npx", "vite", "--host", "0.0.0.0"]
