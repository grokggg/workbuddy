# 05-network-verify-burn — 网络验证 + 用完即焚(服务端按需加载 + 用完即删)

> 评论区提到能力: "网络验证+用完即焚"。
> 机制(中性描述): 一次性令牌签发 -> 验证时服务端按需加载内容 -> 使用后烧毁
> (令牌立即失效 + 内容从缓存删除)。
> 注: 学术向服务端设计(令牌生命周期 / 按需加载 / 状态审计研究),
> 不用于真实绕过授权或付费墙。

## 一、模块标识
- 编号: 05 / 位置: comment-capabilities/05-network-verify-burn

## 二、模块功能
- 输入: 内容标识 key(可选直给内容)+ 有效期; 或待验证/烧毁的令牌
- 输出: 一次性令牌; 验证通过的临时加载内容; 烧毁确认; 活跃/已烧毁审计

## 三、模块代码

### 3.1 核心引擎 `lib/engine.py`

`BurnServer`(模拟服务端), 四个能力 + 可注入存储:

- (a) `issue_token(key, ttl, content)` — 签发一次性令牌(带过期)
- (b) `verify(token)` — 验证令牌 + 返回临时加载内容(按需加载)
- (c) `burn(token)` — 使用后立即烧毁(令牌失效 + 内容删除)
- (d) `audit()` — 状态审计: 活跃/已烧毁令牌列表

```python
from lib.engine import BurnServer

srv = BurnServer(ttl=300.0)                       # 内存 dict 存储
r = srv.issue_token("note.md", content="机密")    # 签发
v = srv.verify(r["token"])                        # 验证 + 返回内容
b = srv.burn(r["token"])                          # 用完即焚
srv.audit()                                       # 状态审计
```

关键设计:

- **一次性语义**: 验证成功即标记已使用(uses=1), 再次验证返回
  `already_used`; 只有 `burn` 才正式烧毁。
- **按需加载**: 签发时不传 `content`, 内容在 `verify` 时才经
  `loader(key)` 惰性加载; 加载失败返回 `load_failed`。
- **用完即删**: `burn` 把令牌置为 `burned` 并删除缓存内容。
- **注入点**: `store`(任意 mapping 存储层)、`loader`、`token_factory`、
  `now_fn`(假时钟, 测试用)、`ttl`。

### 3.2 CLI `cli.py`

```bash
python3 cli.py issue --key note.md --content '机密'   # 签发
python3 cli.py verify <TOKEN>                          # 验证
python3 cli.py burn <TOKEN>                            # 烧毁
python3 cli.py audit                                   # 审计
python3 cli.py demo        # 单进程完整生命周期演示(签发->验证->烧毁->审计)
```

> 注: 模拟服务端为内存存储, 每条 `cli.py` 命令是独立进程, 令牌不跨进程
> 共享; 要看完整生命周期请用 `demo`。

### 3.3 安装脚本 `install.sh`

`bash install.sh` — 语法检查 + 全量测试 + CLI 冒烟(demo 完整生命周期)。

## 四、模块边界
- 模拟服务端, 内存存储, 进程退出即清零(不落盘、不联网)
- 一次性令牌语义: 验证一次后即拒绝重复使用, 烧毁后彻底失效
- 烧毁即删除缓存内容, 不保留任何明文副本
- 业务失败统一返回 `{ok: False, reason: ...}` 字典, 不抛异常

## 五、模块接口
- `BurnServer(store=None, loader=None, ttl=300.0, token_factory=None, now_fn=None)`
- `issue_token(key, ttl=None, content=None) -> {ok, token, key, issued_at, expires_at}`
- `verify(token) -> {ok, token, key, content, expires_at} | {ok: False, reason}`
- `burn(token) -> {ok, token, key, content_deleted} | {ok: False, reason}`
- `audit() -> {active, burned, active_count, burned_count}`
- `active_tokens() / burned_tokens() -> List[str]`

## 六、模块测试
见 `tests/test_engine.py`(19 例, `python3 tests/test_engine.py` 全绿),
覆盖: 签发(默认/自定义 TTL、非法 key、按需加载延迟)、验证(成功/未知/烧毁后/
过期/过期后烧毁/重复使用/加载失败/无内容)、烧毁(失效+删内容/未知/重复)、
审计(活跃与烧毁列表/使用后未烧毁仍活跃)、存储注入(自定义存储层生效)。

## 七、模块依赖
- Python 3.8+ 标准库(secrets/time/argparse/unittest), 无第三方依赖

## 八、集成说明
- 与 01-agents-md-universal 同风格: lib/ 引擎 + tests/ 单元测试 + CLI + 安装脚本
- 存储层可注入, 便于替换为 Redis/DB(生产化路径)
- 按需加载 + 用完即删为学术向服务端设计研究, 不用于真实绕过授权
