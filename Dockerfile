# 餐饮供应链金融赋能平台 - Dockerfile
# 多阶段构建：后端(Python Flask) + 前端(Nginx)

# ============================================
# 阶段1: Python后端构建
# ============================================
FROM python:3.11-slim AS backend-builder

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY backend/ .

# ============================================
# 阶段2: 前端构建
# ============================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app

# 复制前端文件
COPY frontend/package*.json ./

# 安装依赖（如果有的话）
RUN npm install || echo "No npm dependencies"

# 复制完整前端代码
COPY frontend/ .

# 如果需要构建，运行 build 命令
# RUN npm run build || echo "No build script"

# ============================================
# 阶段3: 生产镜像
# ============================================
FROM python:3.11-slim AS production

# 安装系统依赖和nginx
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 创建应用目录
WORKDIR /app

# 从builder阶段复制Python依赖
COPY --from=backend-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend-builder /usr/local/bin /usr/local/bin

# 复制后端代码
COPY --from=backend-builder /app/backend /app/backend

# 复制前端静态文件
COPY --from=frontend-builder /app /app/frontend

# 复制Nginx配置
COPY nginx.conf /etc/nginx/nginx.conf
COPY frontend/default.conf /etc/nginx/conf.d/default.conf

# 复制docker-compose配置
COPY docker-compose.yml /app/docker-compose.yml
COPY deploy.sh /app/deploy.sh

# 创建非root用户
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# 环境变量
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production
ENV PORT=5000

# 暴露端口
EXPOSE 80 5000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

# 切换到非root用户
USER appuser

# 启动命令
CMD ["sh", "-c", "cd /app/backend && python app.py"]
