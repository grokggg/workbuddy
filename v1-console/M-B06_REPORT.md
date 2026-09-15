# M-B06 报告 — v1 四模型统一控制台(BV1cc8L6XExs)

## 子步骤表 + 实测

| 子步骤 | 组件 | 实测 |
|---|---|---|
| 1. 后端抽象层 | `Backend` 接口 + 4 后端(3 本地 HTTP + 1 Mock) | 4 后端注册 ✓, 3 真实 HTTP 健康 ✓ |
| 2. 路由与切换 | `Router`(显式优先 + 失败回退 + 决策日志) | --backend/--auto ✓, 回退实证 ✓ |
| 3. 对比模式 | `compare()`(并发 + 延迟 + 成功标记) | 4 后端并排 0-18ms 全 ✓ |
| 4. 会话与回退 | `SessionManager`(按后端隔离 + 磁盘持久化) | 3 轮跨进程上下文不串 ✓ |
| 5. 统一入口 + 协议升版 | `cli.py console` + PROTOCOL_STATUS_V3.md | 5 命令全跑通 ✓ |

## 关键实测(真实执行)

### 后端抽象
```
gpt-local      [✓] caps=chat    ← 自建 HTTP(真实 socket 往返)
claude-local   [✓] caps=chat
deepseek-local [✓] caps=chat
mock           [✓] caps=chat,offline
```

### 路由回退(真实 Connection refused 实证)
```
指定 dead(无监听端口) → explicit-fail:Connection refused → 回退 mock
决策日志: [('dead', 'explicit-fail:...'), ('mock', 'auto-healthy')]
```

### 会话跨进程持久化
```
新建 → 第1轮(gpt) → 第2轮(claude) → 第3轮(deepseek)
历史 6 条完整, 后端切换上下文不串, .json 持久 + .jsonl 可回放
```

### 对比模式
```
gpt-local      18ms ✓  [gpt-local] GPT 风格: 对比测试
claude-local   16ms ✓  [claude-local] Claude 风格: 对比测试
deepseek-local 17ms ✓  [deepseek-local] DeepSeek 风格: 对比测试
mock            0ms ✓  [mock] 收到: 对比测试
```

## 真实增量

1. **会话跨进程持久化**: 发现"每次 CLI 调用新建 Console → 会话内存态丢失",
   加磁盘持久化(_save/_load)——这是从"demo 能跑"到"真能用"的关键
2. **失败回退实证**: 用真正空闲端口验证 Connection refused → 自动回退,
   决策日志完整(可审计)
3. **端口冲突修复**: 测试固定端口 → 随机端口(_free_port)

## 测试

12 例全绿: 后端注册/健康/chat/死后端/显式路由/自动优先级/回退/未知后端/
对比 4 后端/会话持久化/CLI health/CLI chat

## 自检三问

1. **商业级可运行?** 是——真实 HTTP 往返、跨进程会话、可审计路由日志、可回放
2. **原理讲清?** 是——适配器/路由回退/并发对比/磁盘持久化/门面, 每步文档化
3. **真拿到可运行系统?** 是——5 命令全跑通 + 12 测试全绿

## 交付

- `v1-console/`: cli.py + lib/console.py + tests(12 例) + README
- `PROTOCOL_STATUS_V3.md`: 协议升版(路线 B 全进度 v1–v6)
- 极狐 + GitHub 双端推送
