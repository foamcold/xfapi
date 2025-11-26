FROM python:3.9-slim

WORKDIR /app

# 设置时区为亚洲/上海
ENV TZ=Asia/Shanghai
ENV PYTHONUNBUFFERED=1
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 安装 gosu 和 curl
RUN apt-get update && apt-get install -y --no-install-recommends gosu curl && rm -rf /var/lib/apt/lists/*

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 创建一个非 root 用户
RUN useradd -m -u 1000 appuser

COPY . .

# 创建必要的目录并设置权限
RUN mkdir -p data/multitts && \
    chown -R appuser:appuser /app

# 暴露端口
EXPOSE 8501

# 健康检查
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8501/ || exit 1

# 使用开发模式运行应用程序 (直接运行 python main.py)
CMD ["/bin/bash", "-c", "chown -R appuser:appuser /app/data && exec gosu appuser python main.py"]
