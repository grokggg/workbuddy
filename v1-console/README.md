# v1-console — 四模型统一控制台(BV1cc8L6XExs 复现)

一个入口, 统一调度 4 个模型后端, 可切换、可对比、可回退。

## 30 秒跑通

```bash
# 后端列表(3 本地 HTTP + 1 mock)
python3 cli.py console --list-backends

# 指定后端对话
python3 cli.py console --backend gpt-local "你好"

# 自动路由(失败回退)
python3 cli.py console --auto "问题"

# 对比模式(4 后端并排, 含延迟)
python3 cli.py console --compare gpt-local,claude-local,deepseek-local,mock "问题"

# 会话(新建 → 多轮 → 切后端)
python3 cli.py console --new-session
python3 cli.py console --session <id> "第一轮" --backend gpt-local
python3 cli.py console --session <id> "第二轮" --backend claude-local

# 健康检查
python3 cli.py console --health
```

## 架构(5 子步骤)

| 子步骤 | 组件 | 原理 |
|---|---|---|
| 1. 后端抽象 | `Backend` 接口 + 4 后端 | 适配器模式收敛差异 |
| 2. 路由切换 | `Router` | 显式优先 + 失败回退 + 决策日志 |
| 3. 对比模式 | `compare()` | 并发调用 + 并排结果 |
| 4. 会话回退 | `SessionManager` | 按后端隔离 + 磁盘持久化 + 可回放日志 |
| 5. 统一入口 | `cli.py console` | 门面屏蔽后端差异 |

## 后端

- `gpt-local` / `claude-local` / `deepseek-local`: 自建本地 HTTP server
  (真实 socket/HTTP 往返, 每个固定风格回复)
- `mock`: 规则回复兜底, 永远可用

无外部 API key 即可跑全链路; 有 key 时在 `LocalHTTPBackend` 子类
里换真实 provider endpoint 即可。

## 数据

- 工作目录: `$V1_CONSOLE_DIR` 或 `/tmp/v1-console/`
- `logs/router.log`: 每次路由决策(可审计)
- `sessions/<id>.json`: 会话状态(跨进程持久)
- `sessions/<id>.jsonl`: 对话日志(可回放)

## 测试

```bash
python3 tests/test_console.py   # 12 例全绿
```
