FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn \
    PIP_DEFAULT_TIMEOUT=120

# cairo 为 PNG/PDF 导出所需；国内 apt 默认源也偶尔慢，可视需要换成 mirrors.tencentyun.com
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先复制依赖文件，利用 Docker 缓存
COPY pyproject.toml ./
COPY app ./app

# 安装；省略 [dev] 不带测试依赖
# PIP_INDEX_URL 通过 ENV 注入清华镜像，国内可避免 pypi.org/pythonhosted 超时
RUN pip install --no-cache-dir .

RUN mkdir -p /app/data /app/logs

ENV DATABASE_URL="sqlite+aiosqlite:////app/data/talk2graph.db" \
    LOG_DIR=/app/logs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
