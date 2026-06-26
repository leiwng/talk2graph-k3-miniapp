#!/usr/bin/env bash
# 每日把 SQLite 备份到腾讯云 COS。
#
# 依赖：
#   - sqlite3
#   - coscli（https://cloud.tencent.com/document/product/436/63143）
#   - 已 `coscli config init` 完成（推荐为该桶单独建子用户 SecretId/SecretKey）
#
# 加入 crontab：
#   T2G_ROOT=/opt/talk2graph-glm
#   T2G_COS_BUCKET=cos://talk2graph-1259138134
#   0 3 * * * /opt/talk2graph-glm/deploy/backup-db.sh >> /var/log/t2g-backup.log 2>&1

set -euo pipefail

ROOT="${T2G_ROOT:-/opt/talk2graph-glm}"
BUCKET="${T2G_COS_BUCKET:-cos://talk2graph-1259138134}"
DB="$ROOT/data/db/talk2graph.db"

if ! command -v sqlite3 >/dev/null 2>&1; then
    echo "[backup] ❌ 未找到 sqlite3，请先 'sudo apt install -y sqlite3'"
    exit 1
fi

if ! command -v coscli >/dev/null 2>&1; then
    echo "[backup] ❌ 未找到 coscli。安装："
    echo "  wget https://cosbrowser.cloud.tencent.com/software/coscli/coscli-linux-amd64 -O /tmp/coscli"
    echo "  sudo mv /tmp/coscli /usr/local/bin/coscli && sudo chmod +x /usr/local/bin/coscli"
    echo "  coscli config init  # 填子用户 SecretId/SecretKey + bucket=talk2graph-1259138134 + region=ap-guangzhou"
    exit 1
fi

if [ ! -f "$DB" ]; then
    echo "[backup] ❌ DB not found: $DB"
    exit 1
fi

DATE=$(date +%Y%m%d-%H%M%S)
LOCAL="$ROOT/data/backups/talk2graph-$DATE.db"
mkdir -p "$(dirname "$LOCAL")"

# SQLite 安全备份（不锁库）
sqlite3 "$DB" ".backup '$LOCAL'"

# 上传 COS
coscli cp "$LOCAL" "$BUCKET/db/talk2graph-$DATE.db"

# 保留本地最近 7 天
find "$ROOT/data/backups" -name 'talk2graph-*.db' -mtime +7 -delete || true

echo "[backup] ✅ $LOCAL → $BUCKET/db/talk2graph-$DATE.db"
