# v6-skill-router — 参考实现层

> 补全三个核心部件的**格式模板 + 示例填充 + 命令模板 + 完整流程**。
> 全部占位符化,不构成可运行的破解载荷;槽位与调用方式与 BV13nTj6JEWT 蒸馏文档对齐。

---

## 1. 路由表 —— 完整格式模板

### 1.1 通用模板

```yaml
version: {VERSION}
default_skill: {DEFAULT_SKILL_ID}
skills:

  - id: {SKILL_ID}
    name: {SKILL_NAME}
    role: {ROLE}                    # 通用 / 专项 / 元技能
    triggers:
      - "{TRIGGER_REGEX_1}"          # 例: "定位.*sign"
      - "{TRIGGER_REGEX_2}"          # 例: "极验|geetest|GT4"
    boundary: |
      {BOUNDARY_STATEMENT}           # 例: "只做定位, 不做 AST 解混淆。交给 xxx"

# 冲突消解顺序: 专项 > 通用 > 元技能
priority:
  - {SPECIFIC_SKILL_1}
  - {SPECIFIC_SKILL_2}
  - {GENERAL_SKILL_1}
  - {DEFAULT_SKILL_ID}
```

### 1.2 示例填充 —— 新增一个 skill(协议还原)

```yaml
  - id: web-protocol-recovery
    name: web-protocol-recovery
    role: 专项·协议
    triggers:
      - "协议还原|协议恢复|browser-free"
      - "还原成纯 Python|多层加密"
    boundary: |
      完整分层协议(多层加密+解码+传输包装), 必须输出协议图谱。
      不做: 单步签名定位(find-crypto-entry)、AST 解混淆(ast-deobfuscate)。
```

### 1.3 路由决策流程(完整)

```
输入 query
  │
  ▼
[1] 归一化: NFKC + 小写 + 去空格标点
  │   例: "极验 GT4 滑块, 走 gt4!" → "极验gt4滑块走gt4"
  │
  ▼
[2] 逐 skill 编译 triggers(正则)
  │   规则: 含 .* / ( ) / [ ] 视为正则; 否则按 | 拆字面
  │
  ├── 命中 → 记录 RouteHit(skill_id, trigger, score)
  │         分值 = 0.6 + min(0.4, 命中长度/20)
  │
  └── 未命中 → 跳过
  │
  ▼
[3] 无命中 → 兜底 default_skill(skill-creator)
  │
  ▼
[4] 有命中 → 按 priority 顺序取第一个命中的(专项优先)
  │   例: 输入同时命中 gt4 和 v8-web-reverse → 取 gt4(priority 更高)
  │
  ▼
[5] 输出 RouteDecision(query, hits[], winner, fallback)
```

---

## 2. iv8 引擎接口 —— 完整行为契约 + 命令模板

### 2.1 接口完整定义(占位符)

```python
class IV8Backend:
    """iv8 引擎统一接口。真 iv8 是闭源 C++ 扩展, 本接口是行为契约。"""

    name = "base"

    def __init__(self, time_mode: str = "logical"):
        self.time_mode = time_mode       # "logical" = 逻辑时间, 瞬间推进

    # 生命周期
    def __enter__(self): ...             # start()
    def __exit__(self, *exc): ...        # stop()
    def start(self): ...                 # 初始化上下文
    def stop(self): ...                  # 释放上下文

    # 核心能力(对应蒸馏文档 7 项)
    def eval(self, js: str): ...         # 执行 JS, 返回结果
    def expose(self, data, name="data"): ...  # 注入数据 → window.iv8.<name>
    def load_page(self, base_url, html): ...  # 流式加载 HTML+JS, 触发 DOMContentLoaded
    def advance(self, ms): ...           # 推进逻辑事件循环(瞬间完成)
    def netlog(self): ...                # 返回全部 XHR/fetch 的 url/method/headers/body
    def get_cookie(self): ...            # 读 document.cookie
    def trusted_input(self, event_type, **fields): ...  # 派发 isTrusted=true 事件
```

### 2.2 真 iv8 调用命令模板

```python
import json
from iv8_silent import import_iv8_silent

iv8 = import_iv8_silent()                 # 静默导入, 屏蔽版本横幅

with iv8.JSContext(time_mode="logical") as ctx:
    # [1] 执行 JS
    ua = ctx.eval("navigator.userAgent")          # → Mozilla/5.0 (Windows NT 10.0; ...)

    # [2] 注入数据
    ctx.expose({"seed": "abc123"}, "pageData")    # → window.iv8.pageData

    # [3] 加载页面(流式解析 + 按序执行 <script> + 触发 DOMContentLoaded)
    payload = json.dumps({"baseURL": "https://{HOST}/", "html": html})
    ctx.eval(f"window.__iv8__.page.load({payload})")

    # [4] 推进逻辑时间(瞬间完成, 不用真 sleep)
    ctx.eval("window.__iv8__.eventLoop.advance(3000)")

    # [5] 捕获网络
    logs = json.loads(ctx.eval("JSON.stringify(window.__iv8__.netLog.entries)"))
    #   → [{"url": "https://{HOST}/api/track?sign=...", "method": "GET", ...}]

    # [6] 读 cookie
    cookie = ctx.eval("document.cookie")          # → "__sign=abc123; ..."

    # [7] 可信输入(滑块验证码行为数据)
    ok = ctx.eval("window.__iv8__.input.dispatchPointerEvent({"
                  "type: 'pointerdown', clientX: 100, clientY: 150,"
                  "button: 0, buttons: 1, pointerId: 1, pointerType: 'mouse',"
                  "isPrimary: true})")
    #   → True (isTrusted=true)
```

### 2.3 两种后端的行为差异

| 能力 | MockIV8Backend | RealIV8Backend |
|---|---|---|
| `eval` | 关键字模拟 | 真 V8 执行 |
| `load_page` | 正则模拟 cookie/XHR | 真 DOM 解析 + script 执行 |
| `advance` | 空操作 | 真逻辑时间推进 |
| `netlog` | 预置 1 条 | 真捕获全部 XHR/fetch |
| `trusted_input` | 恒 True | 真派发 isTrusted=true |
| 依赖 | 无 | `pip install iv8` |

---

## 3. 案例回血 —— 完整流程

### 3.1 触发条件

仅在用户明确要求"把本次成果沉淀为案例 / 回写到 skill"时启用。默认不回写。

### 3.2 完整流程

```
[1] 选择分类目录
    signatures/ | js-challenges/ | browser-tokens/ | network-hook-signing/ | captcha/

[2] 命名 slug
    规则: [a-z0-9][a-z0-9-]{2,48}  例: site-feature.py
    ⚠️ 防路径注入: 不允许空格/大写/特殊字符

[3] 只复制"已验证的最小可复用"脚本
    保留真实案例所需字段原文(URL/headers/params/cookies/JS 入口)
    去掉调试残留(print/临时变量/一次性逻辑)

[4] 写文件 + 自动头部
    # 案例回血自动生成
    # slug: {slug}
    # category: {category}
    # generated_at: {时间}
    # case_id: {uuid}
    # meta: {json}

[5] 更新 example-taxonomy.md
    追加: - {category}/{slug}.py — {描述}
    更新目录树与选择规则

[6] 仅当新案例暴露了"通用写法"时才更新 SKILL.md 规则章节
    不要为单站点细节污染通用规则
```

### 3.3 命令模板

```bash
# 回写一个案例
python3 cli.py regen js-challenges my-case ./case.py \
        --desc "challenge cookie 案例" \
        --skill-root ./v8-web-reverse

# 验证回写
ls ./v8-web-reverse/references/cases/js-challenges/my-case.py
grep "my-case" ./v8-web-reverse/references/example-taxonomy.md
```

### 3.4 分类选择规则(对应蒸馏文档)

| 场景 | 分类 | 落点 |
|---|---|---|
| 签名写在 cookie 里 | `js-challenges/` | challenge 页面 cookie |
| 签名在 URL 后缀/header 且运行时拼出 | `network-hook-signing/` | netLog 捕获 XHR |
| 需要先过验证码(滑块/TDC) | `captcha/` | 可信输入路径 |
| 纯算法签名(无浏览器态) | `signatures/` | 静态算法还原 |
| 浏览器 token(cookie/token 由 JS 生成) | `browser-tokens/` | JS 生成 token |
