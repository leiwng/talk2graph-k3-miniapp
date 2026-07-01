# W11 上线腾讯云操作手册

> 目标：把 W10（v0.10.0）→ W11（v0.11.0）。测试 103 → 115。
>
> **W11 无 DB schema 变更**，一步到位。

## 一句话升级

```bash
ssh <user>@49.233.15.73
cd ~/talk2graph-glm
./deploy/bootstrap.sh
```

bootstrap.sh 会自动：
1. `git fetch origin main` → 拉到 v0.11.0（commit 8cb2cef）
2. `git reset --hard origin/main`
3. `docker compose build` → 重建镜像
4. `docker compose up -d` → 启动
5. 健康检查 60s 内绿灯

## 事前准备（推荐）

```bash
cd ~/talk2graph-glm

# 备份 DB（W11 无 schema 变更，但保险起见）
docker exec t2g-backend sh -c "cp /app/data/talk2graph.db /app/data/backups/pre-w11-$(date +%Y%m%d-%H%M%S).db"

# 记录当前 tag（回滚锚点）
git describe --tags --always
# 期望：v0.10.0
```

## 升级后验证（2 步）

### 1. 健康检查
```bash
curl -s http://localhost:8080/api/health
# 期望：{"status":"ok",...}
```

### 2. 端到端手测 3 句

浏览器打开 `http://49.233.15.73:8080/`（**必须 Ctrl+F5 强制刷新** 清 JS 缓存），点「+ 新会话」：

| # | 输入 | 期望 |
|---|---|---|
| A | `画三角形 ABC，AB=4，BC=3，∠B=60°；作三角形 ABC 关于点 B 的中心对称图形 A'B'C'` | 两个三角形，虚线派生 |
| B | `画直角三角形 ABC，∠ABC=90°，AB=1，BC=2；将线段 AC 绕点 A 旋转 90° 得到线段 AD` | 出现 D 点 + AD 线段 |
| C | `画一个等边三角形 ABC，边长为 4` | 老题不退化 |

## 应急回滚

### 回到 W10
```bash
cd ~/talk2graph-glm
git checkout v0.10.0
docker compose up -d --build
```
（W11 → W10 无 schema 差异，fallback 列在 W10 已存在）

### 回到 W8（跳过 W9/W10/W11）
```bash
git checkout v0.8.0
# W10 的 fallback 列会残留在 DB 但 W8 代码不读，兼容
docker compose up -d --build
```

## 常见问题

### git fetch 失败
```bash
T2G_GIT_MIRROR=https://kkgithub.com/leiwng/talk2graph-glm.git ./deploy/bootstrap.sh
```

### 前端仍显示旧行为
浏览器缓存。用户需要 Ctrl+F5 或隐私窗口。

## 完成后

在 `docs/operations.md` 记一笔"W11 上线 YYYY-MM-DD"。
