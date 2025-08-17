# 使用基于 Alpine Linux 的 Python 镜像
FROM python:3.11-alpine

# 设置工作目录
WORKDIR /app

# 复制 requirements.txt 文件并安装依赖
# 这是利用 Docker 构建缓存的最佳实践
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制你的应用代码
COPY . .
ENV TZ=Asia/Shanghai

# 你的启动命令
CMD ["python3", "-u", "main.py"]
