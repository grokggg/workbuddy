# 03-relay-manager — 中转站管理(多端点管理 + 切换 + 健康检查)

> 评论区提到能力: "多 LLM API 端点(中转站)的管理: 注册 / 切换 / 健康检查"。
> 机制: RelayManager 统一管理多个 relay 端点(base_url / api_key_env / model / 权重),
> 按健康度/权重/轮询切换, urllib 探活, JSON 配置持久化(不落明文 key)。
> 纯 Python 3.8+ 标准库, 无第三方依赖。

## 一、模块标识
- 编号: 03 / 位置: comment-capabilities/03-relay-manager
- 参考: 01-agents-md-universal 的 lib/ + tests/ 结构

## 二、模块功能
- 输入: 端点定义(name / base_url / api_key_env / model / weight) + 健康检查命令
- 输出: 健康检查结果 / 切换选中的端点 / JSON 配置文件
- transport 抽象: BaseTransport(接口) + FakeTransport(离线测试) + UrllibTransport(真联网)

## 三、模块代码
### 3.1 引擎 `lib/engine.py`
- `RelayManager.add_relay(name, base_url, api_key_env, model, weight)` — 端点注册, 重名/非法 URL/负权重抛 `RelayError`
- `RelayManager.select(strategy, check_first)` — 端点切换: `health`(排除故障, 权重加权)/ `weight`(纯权重)/ `round_robin`(轮询)/ `first`(注册序); `check_first=True` 先探活再选
- `RelayManager.check(name, transport, timeout)` — 健康检查: 对全部/指定端点探活, 更新 health/status/latency_ms/last_check/error
- `RelayManager.list_relays() / stats()` — 端点列表 / 统计(总数、健康、故障、未检查、平均延迟)
- `RelayManager.save_config(path) / load_config(path) / from_config(path)` — JSON 配置持久化(原子写, 校验版本, 自动加载); 只存 api_key_env 环境变量名, 不存明文 key 与运行时健康状态

### 3.2 transport 抽象(同一文件)
```python
class BaseTransport:      # probe(base_url, timeout) -> {ok, status, latency_ms, error}
class FakeTransport:      # 离线: routes{url:行为} / default / fail_all, 统计 probe_count
class UrllibTransport:    # 真联网: urllib 请求, status<500 视为存活(401/403/404/429 说明网关在线)
```

### 3.3 CLI `cli.py`
- `add --name --base-url [--api-key-env --model --weight]` — 注册端点并保存配置
- `list [--stats]` — 列出端点健康状态, 可选统计
- `check [--name --timeout]` — 探活全部/指定端点
- `switch [--strategy --check-first --timeout]` — 切换端点(health/weight/round_robin/first)

### 3.4 安装 `install.sh`
复制到 `~/.local/bin/relay-manager` 并做单元测试自检。

## 四、模块边界
- 只依赖 Python 3.8+ 标准库(urllib/json/os)
- API key 只从环境变量读取, 配置文件永不落明文
- 健康判定: `status < 500` 视为存活, 连接失败/超时/5xx 视为故障
- 默认配置路径 `~/.relay-manager/config.json`, 可用 `RELAY_CONFIG` 环境变量覆盖

## 五、模块接口
- `add_relay(name, base_url, api_key_env=None, model=None, weight=1.0) -> dict`
- `select(strategy="health", check_first=False, transport=None, timeout=5.0) -> dict|None`
- `check(name=None, transport=None, timeout=5.0) -> {name: probe_result}`
- `list_relays() -> [dict]` / `stats() -> dict`
- `save_config(path=None) -> path` / `load_config(path) -> int` / `RelayManager.from_config(path)`
- transport: `probe(base_url, timeout) -> {ok, status, latency_ms, error}`

## 六、模块测试
见 tests/test_engine.py(26 例): 注册 / 列表统计 / 健康检查(注入 transport) / FakeTransport / 切换(health/weight/轮询/first) / 配置持久化 / 边界(明文 key 不入库、未知策略、非法参数)。
运行: `python3 tests/test_engine.py`

## 七、模块依赖
- Python 3.8+ 标准库

## 八、集成说明
- 与 01-agents-md-universal 同构(lib/engine.py + tests/test_engine.py + cli.py + install.sh + README.md)
- 切换策略可按需扩展: 在 `select()` 中加分支即可, 不影响其他模块
