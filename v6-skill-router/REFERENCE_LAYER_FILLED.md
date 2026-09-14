# v6-skill-router — 参考实现层(填充版)

> 依据: BV13nTj6JEWT 字幕(`BV13nTj6JEWT_字幕.txt` 32 段)。
> 核心: 11 Skills 路由网 + iv8(字幕里叫 MV8)替代 Node 补环境 + 案例回血 + 边界移交。
> 填充到命令级即停止;不生成可执行的破解链。

---

## 0. 视频字幕核心内容

| 时间 | 字幕 | 对应实现 |
|---|---|---|
| 8.85s-15.73s | "5月份一整个月优化调试, 6月初落地" | 11 skill 集合 |
| 15.95s-30.23s | "补环境 / 定位加密参数 / 追踪调用链 / AST 解混淆 / 协议 / Cookie / WSM" | 通用型 skill |
| 30.43s-43.87s | "极验专项 / 腾讯滑块专项 / V8补环境专项 / 瑞数专项 / WAF Cookie专项" | 专项型 skill |
| 44.29s-55.65s | "分 Skills 就可以分成通用的以及这种专项的" | 路由分类: 通用 vs 专项 |
| 63.73s-69.49s | "生成一个紧凑可运行的 Python 脚本, 基于 MV8" | v8-web-reverse 交付物 |
| 71.47s-84.87s | "Python 联动 C++, 内置浏览器环境" | iv8 = Python C++ 扩展 |
| 85.03s-92.81s | "以前补环境要 Node.js + 环境代理吐出环境日志" | 旧方案 |
| 93.09s-108.65s | "现在直接 MV8 执行脚本, 不需要 Node" | 新方案 |
| 114.81s-126.15s | "某东 / 某多多 / 某红书 / 瑞数三四五六全部通杀" | 案例库(真实站点) |
| 140.83s-168.53s | "案例回血: 实现案例自动回写到 Skills, 下次参考" | CaseRegen 自动回写 |
| 195.36s-210.37s | "边界: 做什么需求交给另外更适合的 Skills" | boundary 移交规则 |
| 221.64s-240.98s | "后续做 MCP 接魔改浏览器 / 指纹浏览器" | 后续规划(未实现) |

---

## 1. 路由表 —— 填充版

### 1.1 11 个 skill 完整路由表(按字幕 + 蒸馏文档)

| # | skill_id | 类型 | 触发词(实际) | 边界移交 |
|---|---|---|---|---|
| 1 | skill-creator | 元技能 | 创建/修订/评估 skill | 兜底 |
| 2 | env-patch | 通用 | 补环境 / Node 沙箱 | → find-crypto-entry / ast-deobfuscate |
| 3 | find-crypto-entry | 通用 | 定位 sign/token/加密参数 | → ast-deobfuscate |
| 4 | ast-deobfuscate | 通用 | 解混淆 / obfuscator.io | → find-crypto-entry |
| 5 | web-protocol-recovery | 专项 | 协议还原 / browser-free | 必须输出协议图谱 |
| 6 | gt4-protocol-reverse | 专项 | 极验 / GT4 / pow_msg | → v8-web-reverse(可信输入) |
| 7 | tencent-slide-tdc-env | 专项 | 腾讯滑块 / TDC | 定向补环境 |
| 8 | v8-web-reverse | 专项 | iv8 / 紧凑 Python 脚本 | → find-crypto-entry / ast-deobfuscate |
| 9 | browser-hook-snippets | 专项 | hook / 监控 XHR | 只注入观察 |
| 10 | rs-reverse | 专项 | 瑞数 / r2mka / 412 | 固定项目结构 |
| 11 | waf-cookie-pure-first | 专项 | WAF / challenge cookie | 优先纯 Python |

### 1.2 路由决策流程(填充版)

```
输入: "帮我补环境跑这个某东的 a_bogus"
  │
  ▼
[1] 归一化: "帮我补环境跑这个某东的abogus"
  │
  ▼
[2] 匹配:
  │   env-patch: "补环境" 命中
  │   v8-web-reverse: "补环境" 也命中(但需要 iv8 组合词)
  │
  ▼
[3] 冲突消解(priority: 专项 > 通用):
  │   env-patch 是通用 → 先看专项
  │   没有专项命中 → 取 env-patch
  │
  ▼
[4] 输出: env-patch
```

---

## 2. iv8 引擎接口 —— 填充版(按字幕 + 蒸馏文档)

### 2.1 iv8 是什么(字幕 71.47s-108.65s)

> "Python 联动 C++ 内置浏览器环境" → `pip install iv8`(Python C/C++ 扩展, 内嵌 V8)
> "以前补环境要 Node.js + 环境代理" → 旧方案
> "现在直接 MV8 执行脚本, 不需要 Node" → 新方案

### 2.2 完整接口(实际参数已填)

```python
import json
from iv8_silent import import_iv8_silent

iv8 = import_iv8_silent()                 # 静默导入, 屏蔽版本横幅

with iv8.JSContext(time_mode="logical") as ctx:   # logical = 逻辑时间, 瞬间推进
    # [1] 执行 JS
    ua = ctx.eval("navigator.userAgent")
    #   → "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ..."
    #   字幕: "Python 联动 C++ 内置浏览器环境"

    # [2] 注入数据 → window.iv8.pageData
    ctx.expose({"seed": "abc123"}, "pageData")

    # [3] 加载页面(流式解析 + 按序执行 <script> + 触发 DOMContentLoaded)
    payload = json.dumps({"baseURL": "https://{HOST}/", "html": html})
    ctx.eval(f"window.__iv8__.page.load({payload})")
    #   字幕: "可以直接用 MV8 让它去执行那个脚本, 调它内置的浏览器接口"

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

### 2.3 两种后端行为差异(实际参数)

| 能力 | MockIV8Backend | RealIV8Backend |
|---|---|---|
| `eval(js)` | 关键字模拟 | 真 V8 执行 |
| `expose(data, name)` | 存 dict | `ctx.expose(data, name)` |
| `load_page(base_url, html)` | 正则模拟 cookie/XHR | `window.__iv8__.page.load({...})` |
| `advance(ms)` | 空操作 | `eventLoop.advance(ms)` |
| `netlog()` | 预置 1 条 | `netLog.entries` 真捕获 |
| `trusted_input(type, **fields)` | 恒 True | `dispatchPointerEvent` 真派发 |
| 依赖 | 无 | `pip install iv8` |

---

## 3. 案例回血 —— 填充版

### 3.1 字幕原文(140.83s-168.53s)

> "这个 Skills 还有一个功能叫做自动回血功能, 叫做案例回血功能。
> 当我们用这个 Skills 实现了某一个案例, 它会自动地将这个案例回血到这个 Skills 当中,
> 那么这个时候我们就不需要让它再走进去生成了,
> 你下一次再去用这个 Skills 的时候, 再去逆向同样的案例, 或者同类型的案例,
> 它会自己去参考对应里面的一些案例, 然后来实现对应里面的一些逻辑,
> 能够更快更有效率地产出目前的一个需求。"

### 3.2 回血流程(填充版)

```
[1] 触发条件: 用户明确要求"沉淀为案例 / 回写到 skill"
  │
  ▼
[2] 选分类: signatures/ | js-challenges/ | browser-tokens/ | network-hook-signing/ | captcha/
  │
  ▼
[3] 命名 slug: [a-z0-9][a-z0-9-]{2,48}  例: jd-h5st.py
  │
  ▼
[4] 只复制已验证的最小可复用脚本
  │   保留: URL/headers/params/cookies/JS 入口
  │   去掉: 调试残留
  │
  ▼
[5] 写文件 + 自动头部(case_id/slug/category/meta)
  │
  ▼
[6] 更新 example-taxonomy.md
  │
  ▼
[7] 仅当暴露"通用写法"时才更新 SKILL.md 规则章节
```

### 3.3 命令模板(填充版)

```bash
# 回写一个案例
python3 cli.py regen js-challenges jd-h5st ./case.py \
        --desc "某东 h5st 案例" \
        --skill-root ./v8-web-reverse

# 验证回写
ls ./v8-web-reverse/references/cases/js-challenges/jd-h5st.py
grep "jd-h5st" ./v8-web-reverse/references/example-taxonomy.md
```

### 3.4 分类选择规则(填充版)

| 场景 | 分类 | 落点 |
|---|---|---|
| 签名写在 cookie 里 | `js-challenges/` | challenge 页面 cookie |
| 签名在 URL 后缀/header 且运行时拼出 | `network-hook-signing/` | netLog 捕获 XHR |
| 需要先过验证码(滑块/TDC) | `captcha/` | 可信输入路径 |
| 纯算法签名(无浏览器态) | `signatures/` | 静态算法还原 |
| 浏览器 token(JS 生成) | `browser-tokens/` | JS 生成 token |

---

## 4. 边界移交 —— 填充版(字幕 195.36s-210.37s)

> "在这里面它还会有对应的一些边界, 就比如说做什么什么需求的时候,
> 可以去交给另外的一些更适合的 Skills 来去实现。
> 补环境的话要用 node, 就交给他(env-patch)。
> 所以这个时候我们就可以去让 AI 整个去调度这样的一个 Skills。"

| 场景 | 交给 |
|---|---|
| 只定位 sign/token 入口 | find-crypto-entry |
| AST 解混淆 | ast-deobfuscate |
| 通用 Node 补环境 | env-patch |
| 瑞数固定项目结构 | rs-reverse |
| 完整分层协议 | web-protocol-recovery |
| 滑块行为数据 | v8-web-reverse(可信输入) |

---

## 参考实现层

- [REFERENCE_LAYER.md](REFERENCE_LAYER.md) — 格式模板(占位符版)
- [REFERENCE_LAYER_FILLED.md](REFERENCE_LAYER_FILLED.md) — 填充版(按视频转录填实)

