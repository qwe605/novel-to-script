# ===== Python backend =====
FROM python:3.12-slim

WORKDIR /app

# 1) scripts/ 依赖（核心转换逻辑）
COPY scripts/requirements.txt /app/scripts/requirements.txt
RUN pip install --no-cache-dir -r /app/scripts/requirements.txt

# 2) backend/ 依赖（FastAPI + uvicorn）
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# 3) 复制全部代码
COPY scripts/   /app/scripts/
COPY backend/   /app/backend/
COPY schema/    /app/schema/
COPY examples/  /app/examples/

# 4) 将 scripts/ 加入 PYTHONPATH（converter.py 内部也会动态加，这里提前设好）
ENV PYTHONPATH=/app/scripts:$PYTHONPATH

# 5) 输入/输出目录
RUN mkdir -p /app/backend/uploads /app/backend/results /app/backend/tasks

EXPOSE 8000

WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
