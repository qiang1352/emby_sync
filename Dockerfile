FROM python:3.11-alpine3.19 AS builder
WORKDIR /wheels
# 只保留最小编译依赖（可选：加快构建）
RUN apk add --no-cache gcc musl-dev
COPY app/requirements.txt .
# 直接安装预编译 wheel
RUN pip install --upgrade pip==25.2 && \
    pip wheel --no-cache-dir --no-deps -w /wheels -r requirements.txt

FROM python:3.11-alpine3.19
ENV TZ=Asia/Shanghai
RUN apk add --no-cache tzdata && \
    cp /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
WORKDIR /app
COPY --from=builder /wheels/*.whl /tmp/
RUN pip install --no-cache /tmp/*.whl && rm -rf /tmp/*.whl
COPY app/ ./app/
RUN addgroup -g 1000 app && \
    adduser -D -s /bin/sh -u 1000 -G app app && \
    mkdir -p /app/logs && \
    chown -R app:app /app/logs
USER app
CMD ["python", "-m", "app.main"]