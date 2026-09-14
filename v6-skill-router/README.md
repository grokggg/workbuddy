# v6-skill-router — 技能路由架构

> 依据: B站 [BV13nTj6JEWT](https://www.bilibili.com/video/BV13nTj6JEWT)（编程奇遇，AI 逆向 Skills）蒸馏文档。
> 视频核心是 11 个 skill 组成的**路由网**：AI 先扫 `name+description`，命中才读全文，
> 按需读 `references/`，skill 之间用"边界声明"互相移交。
> 本工具把这条"边界声明 → 可执行路由"的机制物化成代码。

## 一、30 秒跑通

```bash
./install.sh            # 环境自检 + 跑全部测试
python3 cli.py demo     # 端到端演示: 路由 + iv8 接口 + 案例回血
```

## 二、三个核心部件

### 1. 路由表 `router_table.yaml`

11 个技能 + 触发规则 + 边界声明 + 冲突消解优先级。

| 部件 | 内容 |
|---|---|
| `skills[].triggers` | 触发词/正则, 命中即路由 |
| `skills[].boundary` | "不该用本 skill 做什么、交给谁" (对应视频边界声明) |
| `priority` | 冲突消解顺序: 专项 > 通用 > 元技能 |

**设计要点**: 宽泛词(如 `cookie`/`sign`)不单独路由, 需与 `iv8`/`执行`/`回放` 组合才命中,
避免"定位 sign 入口"被误派给 v8-web-reverse。

### 2. iv8 引擎接口 `lib/router.py::IV8Backend`

把 iv8 行为契约封装成统一接口, 可替换后端:

| 方法 | 契约 (对应蒸馏文档 7 项) |
|---|---|
| `eval(js)` | 执行 JS |
| `expose(data, name)` | 注入数据, JS 侧 `window.iv8.<name>` |
| `load_page(base_url, html)` | 流式加载 HTML+JS, 触发 DOMContentLoaded |
| `advance(ms)` | 推进逻辑事件循环 (瞬间完成) |
| `netlog()` | 返回全部 XHR/fetch 的 url/method/headers/body |
| `get_cookie()` | 读 `document.cookie` |
| `trusted_input(type, **fields)` | 派发 `isTrusted=true` 的输入事件 |

`create_backend("auto")`: 有真 `iv8` 用真后端, 否则自动落 mock —— **无 iv8 也能跑通全链路**。

### 3. 案例回血 `lib/router.py::CaseRegen`

对应视频"案例回写模式":

```bash
python3 cli.py regen js-challenges my-case ./case.py \
        --desc "challenge cookie 案例" --skill-root ./v8-web-reverse
```

- 分类限 `signatures / js-challenges / browser-tokens / network-hook-signing / captcha`
- slug 必须短且合规 (防路径注入)
- 写案例 + 自动更新 `example-taxonomy.md` 目录树

## 三、CLI

```bash
python3 cli.py route "用 iv8 生成紧凑 Python 脚本回放请求"   # 路由决策
python3 cli.py route-table                                 # 路由表概览
python3 cli.py backend-test                                # iv8 接口契约测试
python3 cli.py regen <cat> <slug> <file> [--desc] [--skill-root]  # 案例回血
python3 cli.py demo                                        # 端到端演示
```

## 四、测试

```bash
./install.sh          # 跑全部 17 例单测
python3 tests/test_router.py -v
```

| 组 | 例数 | 覆盖 |
|---|---|---|
| 归一化 | 3 | NFKC/标点/空 |
| 路由表 | 2 | 加载/缺失 |
| 路由决策 | 6 | 命中/专项优先/兜底 |
| mock 后端契约 | 2 | 行为契约/工厂兜底 |
| 案例回血 | 3 | 写入/taxonomy/非法输入 |
| **合计** | **16+** | 全绿 |

## 五、依赖

- Python 3.8+ (纯标准库)
- 可选: `iv8` (真后端)、`pyyaml` (路由表解析, 缺失时退化 JSON)

## 六、与 v8-web-reverse 集成

1. `regen` 的 `--skill-root` 指向 `reproduce/skills/v8-web-reverse` 时,
   案例直接回写到该 skill 的 `references/cases/`
2. `router_table.yaml` 的 boundary 与 v8-web-reverse SKILL.md 的"不要使用本 skill 当…"逐条对应
3. 真 iv8 后端 (RealIV8Backend) 依赖 `utils/iv8_silent.py` 静默导入, 与 reproduce 一致

---

## 参考实现层

- [REFERENCE_LAYER.md](REFERENCE_LAYER.md) — 格式模板(占位符版)
- [REFERENCE_LAYER_FILLED.md](REFERENCE_LAYER_FILLED.md) — 填充版(按视频转录填实, 含 3 个真实用例)

