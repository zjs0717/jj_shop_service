# jj_shop_service

配合 [jj_shop](../jj_shop) 前端的 FastAPI 后端：用户注册 / 登录、JWT 鉴权、SQLite 用户存储。

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量（首次）
copy .env.example .env

# 3. 启动（默认 http://127.0.0.1:8000）
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

前端 `jj_shop` 的 Vite 已将 `/api` 代理到 `8000` 端口，两边同时启动即可联调。

## 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/auth/register` | 注册，返回 `{ token, username }` |
| `POST` | `/api/auth/login` | 登录，返回 `{ token }` |
| `GET` | `/api/auth/me` | 当前用户，需 `Authorization: Bearer <token>` |
| `GET` | `/health` | 健康检查 |

请求体（注册 / 登录）：

```json
{ "username": "alice", "password": "secret123" }
```

校验规则：用户名 3–50 位，密码 6–128 位。

## 数据存储

- 默认 SQLite：`./app.db`，表 `users`
- 字段：`id`、`username`（唯一）、`password_hash`（bcrypt）、`created_at`
- 可通过环境变量 `DATABASE_URL` 切换数据库

## 环境变量

见 `.env.example`：`SECRET_KEY`、`ACCESS_TOKEN_EXPIRE_MINUTES`、`DATABASE_URL`。
