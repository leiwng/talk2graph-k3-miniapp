#!/usr/bin/env bash
# 一键部署 / 升级脚本（在腾讯云服务器上执行）
#
# 使用：
#   ./deploy/bootstrap.sh                    # 默认对外 8080 端口
#   T2G_HOST_PORT=8081 ./deploy/bootstrap.sh # 自定义端口
#   T2G_RESET_DB=1 ./deploy/bootstrap.sh     # 显式重置 DB（破坏性，谨慎）
#   T2G_SKIP_GIT=1 ./deploy/bootstrap.sh     # 跳过远端拉取，只重建本地代码
#   T2G_GIT_MIRROR=https://kkgithub.com/leiwng/talk2graph-glm.git \
#     ./deploy/bootstrap.sh                  # GitHub 失败时自动重试镜像（国内推荐）

set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"

T2G_HOST_PORT="${T2G_HOST_PORT:-8080}"
export T2G_HOST_PORT

echo "[T2G] 部署根目录：$ROOT"
echo "[T2G] 对外端口   ：$T2G_HOST_PORT"

# 1. 必要文件检查
if [ ! -f backend/.env ]; then
    echo "[T2G] ❌ 未找到 backend/.env"
    echo "       cp backend/.env.example backend/.env && nano backend/.env"
    echo "       至少填入：DEFAULT_PROVIDER=volcengine、VOLCENGINE_API_KEY、VOLCENGINE_ENDPOINT_ID"
    exit 1
fi

# 2. Docker 检查
if ! command -v docker >/dev/null 2>&1; then
    echo "[T2G] 未检测到 docker，尝试自动安装（仅 Debian/Ubuntu）"
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER" || true
    echo "[T2G] 已安装 docker；如果是首次安装请退出 SSH 重新登录后再跑本脚本"
fi
if ! docker compose version >/dev/null 2>&1; then
    echo "[T2G] docker compose 不可用，请升级 Docker"
    exit 1
fi

# 3. 拉最新代码（若是 git 仓库且配了 origin）
fetch_with_fallback() {
    # 先用 origin 试一次；失败且配了 T2G_GIT_MIRROR 时切镜像重试
    if git fetch origin main 2>&1; then
        return 0
    fi
    # 内置一批常用国内镜像（按顺序尝试，任一成功即返回）
    local mirrors=(
        "${T2G_GIT_MIRROR:-}"
        "https://gitclone.com/github.com/leiwng/talk2graph-glm.git"
        "https://ghproxy.com/https://github.com/leiwng/talk2graph-glm.git"
        "https://kkgithub.com/leiwng/talk2graph-glm.git"
        "https://hub.fastgit.xyz/leiwng/talk2graph-glm.git"
    )
    local cur
    cur="$(git remote get-url origin)"
    for m in "${mirrors[@]}"; do
        if [ -z "$m" ]; then
            continue
        fi
        echo "[T2G] ⚠ 尝试镜像：$m"
        git remote set-url origin "$m"
        if timeout 30 git fetch origin main 2>&1; then
            echo "[T2G] ✓ 镜像 fetch 成功：$m"
            return 0
        fi
    done
    echo "[T2G] 所有镜像失败，恢复原 origin"
    git remote set-url origin "$cur"
    return 1
}

if [ -d .git ]; then
    if git remote get-url origin >/dev/null 2>&1; then
        if [ "${T2G_SKIP_GIT:-0}" = "1" ]; then
            echo "[T2G] T2G_SKIP_GIT=1，跳过远端拉取，只重建本地代码"
        else
            echo "[T2G] git fetch + reset --hard origin/main（生产期对齐远端）"
            if ! fetch_with_fallback; then
                echo "[T2G] ❌ git fetch 失败。可选："
                echo "       1) 设置镜像重试：T2G_GIT_MIRROR=https://kkgithub.com/leiwng/talk2graph-glm.git ./deploy/bootstrap.sh"
                echo "       2) 手工切镜像：git remote set-url origin https://kkgithub.com/leiwng/talk2graph-glm.git"
                echo "       3) 跳过拉取重建本地：T2G_SKIP_GIT=1 ./deploy/bootstrap.sh"
                exit 1
            fi
            # 仅当本地无未提交改动时硬对齐
            if [ -z "$(git status --porcelain)" ]; then
                git reset --hard origin/main
                NEW_HEAD=$(git rev-parse --short HEAD)
                echo "[T2G] HEAD 已对齐到 $NEW_HEAD"
            else
                echo "[T2G] ⚠ 检测到本地未提交改动，跳过 reset；如需强制对齐：git stash 后重跑"
            fi
        fi
    else
        echo "[T2G] ⚠ 未配置 git origin，跳过远端拉取。建议："
        echo "       git remote add origin https://github.com/leiwng/talk2graph-glm.git"
    fi
fi

# 4. 创建持久化目录
mkdir -p data/db data/logs data/backups

# 5. DB 幂等处理
if [ "${T2G_RESET_DB:-0}" = "1" ]; then
    if [ -f data/db/talk2graph.db ]; then
        BACKUP="data/backups/pre-reset-$(date +%Y%m%d-%H%M%S).db"
        echo "[T2G] ⚠ T2G_RESET_DB=1，备份并删除现有 DB → $BACKUP"
        cp data/db/talk2graph.db "$BACKUP"
        rm -f data/db/talk2graph.db
    fi
else
    if [ -f data/db/talk2graph.db ]; then
        echo "[T2G] 检测到现有 DB（data/db/talk2graph.db），保留；如需重置请 T2G_RESET_DB=1 重跑"
    fi
fi

# 6. 构建 & 启动
echo "[T2G] docker compose build"
docker compose build

echo "[T2G] docker compose up -d"
docker compose up -d

# 7. 健康检查（走宿主端口）
echo "[T2G] 等待服务就绪…"
for i in {1..30}; do
    if curl -fsS "http://localhost:${T2G_HOST_PORT}/api/health" >/dev/null 2>&1; then
        echo "[T2G] ✅ 部署成功 → http://localhost:${T2G_HOST_PORT}"
        echo "[T2G]    外网访问：http://<服务器公网 IP>:${T2G_HOST_PORT}"
        exit 0
    fi
    sleep 2
done

echo "[T2G] ⚠ 健康检查超时，查看日志：docker compose logs -f"
exit 1
