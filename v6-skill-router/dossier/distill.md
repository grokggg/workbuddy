# 《2026年全新最强AI逆向Skills全网首发》内容蒸馏

> **原始视频**：[B站 BV13nTj6JEWT](https://www.bilibili.com/video/BV13nTj6JEWT)（短链 https://b23.tv/aXx0VMy）
> **UP主**：编程奇遇 | **时长**：4分24秒（264s） | **发布**：2026-07-02
> **蒸馏方式**：官方无CC字幕 → 下载 480P 视频 → Whisper-large-v3 语音转写（33段）+ 抽帧 110 张/去重 39 张 → PaddleOCR 逐帧提取画面文字 → 交叉整合

---

## 一、一句话总结

UP主耗时一个月（5月整月调试、6月初落地）打磨出一套**面向 JS 逆向的 AI Skills 集合**，共 **11 个技能**，覆盖"补环境 / 定位加密参数 / 调用链追踪 / AST 解混淆 / 协议还原 / 瑞数 / 极验GT4 / 腾讯TDC滑块 / V8脚本交付 / 浏览器Hook / WAF Cookie"全链路；核心是**用 iv8（Python 原生 V8 扩展）替代 Node.js 补环境**，直接生成紧凑可运行的 Python 脚本，并带**"案例回血"自进化机制**。

---

## 二、内容时间线（字幕 ↔ 画面对照）

| 时间 | 口播要点 | 同帧画面内容（OCR） |
|---|---|---|
| 00:00–00:10 | 最新版AI逆向Skills，主流大厂加密、瑞数、验证码都能搞定，完整Skills已备好 | **CC Switch → Skills 管理**界面，已安装 11 个技能；右侧标注"最新版AI逆向skill / 爬虫项目skills / 主流大厂加密（某东、某红书、字节等）/ 瑞数系列 / 验证码系列" |
| 00:03–00:10 | 经过5月一整月优化调试，6月初落地 | 网盘目录 `【05】青木老师/爬虫逆向资料/06-skill-20260615`，内含 `逆向skill.zip`、`skill.zip`、`CloakBrowser.zip`（可下载） |
| 00:15–00:43 | 包含补环境、定位加密参数、追踪调用链、协议、Cookie、WSM 等技能点 | 技能清单滚动展示 |
| 00:30–00:55 | 分**通用型**与**专项型**：补环境通用、追踪调用链通用；极验专项、腾讯滑块专项、V8补环境专项、瑞数专项、WAF Cookie专项 | 同上 |
| 01:02–03:42 | 重点讲解 `v8-web-reverse` 技能的实现细节 | Notepad++ 打开 `C:\Users\...\config\opencode\skills\v8-web-reverse\SKILL.md`（**186 行**），全程滚动展示 |
| 02:12–02:20 | 已实现案例：某东、某多多、某红书，瑞数三四五六全通杀，滑块、直聘也能做 | 案例清单（11 个 `.py`） |
| 02:20–02:52 | "案例回血"自动回写功能 | SKILL.md 的"案例回写模式 / 依赖 / 完成报告"章节 |
| 03:05–04:00 | 技能边界：互相移交（如只找入口→find-crypto-entry，AST→ast-deobfuscate） | SKILL.md "触发范围 / 不要使用本skill当…"章节 |
| 04:02–04:24 | 后续规划：自研 **MCP** 接魔改/指纹浏览器 | 回到 CC Switch 技能管理界面 |

---

## 三、技术主线：为什么是 iv8 而不是 Node.js

视频核心论点（00:63–01:84）：

> 以前补环境要 **Node.js** 起一个沙箱，靠环境代理吐出环境日志，再照着日志补 `window`/`navigator`/`document` 等；
> 现在**直接基于 V8 引擎执行目标脚本**——Python 联动 C++，内置了浏览器环境，接口由 C++ 层预置，**不需要 Node**。
> 作者原话：**"通过 Node.js 补环境已经是过去式了。"**

### iv8 是什么（外部资料补全，非视频内容）

[`iv8`](https://pypi.org/project/iv8/) 是一个 **Python C/C++ 原生扩展**，在 C++ 层嵌入 V8 引擎（Chromium 同款），并在 V8 之上用 C++ 实现了大量浏览器 API：

| 能力 | 说明 |
|---|---|
| `iv8.JSContext(environment={...}, time_mode="logical")` | 创建 V8 隔离上下文，注入 navigator / screen / location 等浏览器环境 |
| `ctx.expose(data, name)` | 向 JS 上下文注入数据，通过 `window.iv8.data` 访问 |
| `window.iv8.page.load(...)` | 流式加载 HTML+JS，解析 DOM、按序执行 `<script>`、触发 `DOMContentLoaded` |
| `window.iv8.eventLoop.advance(ms)` | **推进逻辑事件循环**——`sleep(5000)` 在逻辑时间模式下瞬间完成 |
| `window.iv8.netLog.entries` | 捕获 JS 执行期间所有 XHR/fetch 的 url / method / headers / body |
| 可信输入 | 派发 `isTrusted=true` 的 mouse/pointer 事件（滑块验证码关键） |
| `wrapNative` | 把 JS 函数伪装成 `[native code]`，降低补丁可观测差异 |

安装：`pip install iv8`（社区版免费闭源，另有 Pro 版）。相比 jsdom（补环境漏）、Headless Chrome（重、CDP 可被检测），iv8 是**纯 Python 单进程 + 轻资源 + 指纹可控**。

---

## 四、11 个 Skills 全清单

按视频中 CC Switch 界面出现的顺序整理（中文描述为 OCR 还原，已做可读性校正）：

| # | 技能名 | 定位 | 说明 |
|---|---|---|---|
| 1 | **skill-creator** | 元技能 | 创建、修订、评估、打包 OpenCode skills；改进触发准确率、加 evals、迭代对比、benchmark |
| 2 | **env-patch** | 通用·补环境 | 建沙箱补环境。给定 JS 文件、已定位入口或本地 Node 目标时，执行"运行 → 诊断缺失环境 → 补环境 → 功能验证"流程。适合把某东 / a_bogus / SVMP / 瑞数等代码放进 Node.js 沙箱跑通 |
| 3 | **find-crypto-entry** | 通用·定位 | 用源码搜索 + 浏览器 DevTools / MCP 调试能力，定位请求里的**加密参数、摘要参数、签名参数、token、cookie 写入点或安全字段**对应的关键脚本、函数入口和调用链 |
| 4 | **ast-deobfuscate** | 通用·解混淆 | 用 Babel AST 对 JavaScript 做结构化还原，优先处理 **obfuscator.io 风格**（sojson / ob / jsjiami / common 等）清洗流水线，产出可读、可继续分析的源码和中间产物 |
| 5 | **web-protocol-recovery** | 专项·协议 | 把 hostile web client 还原为 **browser-free** 的纯协议实现（多层加密+解码+传输包装）；还原成 Python 脚本时**必须列出协议图谱**，否则判定失败 |
| 6 | **gt4-protocol-reverse** | 专项·极验 | 极验 Geetest **GT4 滑块**验证码协议流程还原与实现：`pow_msg` / `pow_sign`、`lot_number` 派生字段 |
| 7 | **tencent-slide-tdc-env** | 专项·腾讯滑块 | 腾讯滑块 / **TDCaptcha** / `TDC.getData(true)` / `slide.html` 场景定向补环境；用无头浏览器补环境 + 本地代理导出正文、URL 解码等 |
| 8 | **v8-web-reverse** | 专项·交付（**主角**） | 交付**紧凑可运行的 Python 主脚本**：用 iv8 执行浏览器侧 JS，再用 requests / curl_cffi 发真实 HTTP 请求。详见第五节 |
| 9 | **browser-hook-snippets** | 专项·Hook | 在 DevTools / Snippets / 指定上下文注入 hook 脚本，监控 cookie、XHR、fetch、header、storage、WebCrypto、canvas、Worker、Blob、DOM 注入等动态行为 |
| 10 | **rs-reverse** | 专项·瑞数 | 瑞数 / Ruishu / RiverSecurity 轻量项目骨架。**仅在有明确瑞数证据时启用**：`S_tsn` / `sd` / `_` 、`r2mka`、`meta content` Cookie S/T/P、`hasDebug`、瑞数 412/403。创建并维护固定本地项目结构 |
| 11 | **waf-cookie-pure-first** | 专项·WAF Cookie | 站点 Challenge/WAF 动态 cookie 发现（如 `__w_tsfp`、S/T、反爬 cookie），动态探针 cookie。**优先还原纯 Python 协议/算法**，算不动时才退回 v8 执行 |

**分类逻辑**（UP主口播）：
- **通用型**：env-patch（补环境）、find-crypto-entry（追踪调用链）→ 覆盖绝大部分 Web 端逆向技能点
- **专项型**：其余 9 个 → 专门做某一件事

---

## 五、`v8-web-reverse` 深度拆解（视频主体，SKILL.md 共 186 行）

### 5.1 触发范围（该用）

- 明确要求 **Python + iv8 + requests** 跑浏览器 JS 并发真实请求
- 明确要求把 iv8 复现"沉淀为案例 / 回写到 skill / 新增 bundled case"
- 需要 iv8 在浏览器态生成 **cookie、h5st、a_bogus/BDMS 改写 URL、`__zp_stoken__`、动态 header/sign、动态 URL 后缀**，再由 Python 复现真实请求
- 改造 `references/cases/` 里的真实案例为可直接运行的紧凑主脚本
- **412 / 202 / challenge 页面**已确认要用 iv8 执行页面 JS 生成 cookie 或捕获 XHR 后缀
- `rs-reverse` 已确认后缀请求失败，需转为 iv8 执行链先跑通
- 需要 iv8 派发可信 mouse/pointer 事件采集 **TDC / 验证码行为数据**

### 5.2 明确不该用（交接给谁）

| 场景 | 交给 |
|---|---|
| 只定位 sign/token/header 入口、脚本 URL、调用链 | `find-crypto-entry` |
| 只要浏览器 DevTools hook snippet | `browser-hook-snippets` |
| AST 解混淆、控制流还原、字符串数组还原 | `ast-deobfuscate` |
| 通用 Node.js 补环境 | `env-patch` |
| 瑞数固定项目结构、首跳材料缓存、最小 Node/proxy 观察 | `rs-reverse` |
| 瑞数深度算法、r2mka 字节码、URL suffix AST 研究 | 不由本技能接管 |
| 完整分层协议恢复（非紧凑 iv8 脚本） | `web-protocol-recovery` |

### 5.3 硬性约束

1. 自动下载或生成的目标站点动态材料，**统一写入当前工作目录的 `js_reverse_cache/`**（不存在则创建）
2. **不要把新任务的动态素材写进 skill 目录或 `references/cases/`**——只有用户明确要求"沉淀为案例"时才进入回写模式
3. 真实请求链路必须保持**同一个 `requests.Session`** 中的 Cookie、动态 JS、签名参数、时间戳和后缀，**不要混用旧值**

### 5.4 参考文件（references/ 结构）

```
references/
├── api-inventory.md            # iv8 API 索引和内置示例文件导读
├── api-examples/
│   ├── README.md               # iv8 API 示例速查
│   └── *.py                    # context / environment / page.load / eventLoop /
│                               # netLog / 真实网络桥接 / wrapNative / 可信输入 / DevTools
├── example-taxonomy.md         # 真实 examples 的网站逆向分类
├── script-writing-rules.md     # 紧凑主脚本、utils 写法、缓存目录规则
├── case-ingestion-rules.md     # 案例回写时的目录选择、frozen 素材复制、taxonomy 更新
├── reverse-process/index.md    # 真实案例逆向过程索引
├── js-reverse-workflow.md      # 跨 skill 阶段协议（本 skill 覆盖 Port 阶段）
└── cases/
    ├── signatures/             # 签名类
    ├── js-challenges/          # JS 挑战类
    ├── browser-tokens/         # 浏览器 token 类
    ├── network-hook-signing/   # 网络 Hook 签名类
    ├── captcha/                # 验证码类
    └── js_reverse_cache/       # frozen 素材（JD h5st bundle、JD HTML、BDMS runtime）
```

**执行顺序**：先读 `example-taxonomy.md` 选最接近案例 → 查 `reverse-process/index.md`（有逆向过程文档则先读它，否则直接读 case `.py`）→ 需要 API 写法时读 `api-inventory.md` → 若要求回写案例，还要读 `case-ingestion-rules.md`。

### 5.5 输出规则（生成脚本的硬规范）

- 默认生成**一个短主 `.py` 脚本**，同时生成 `utils/iv8_silent.py` 和 `utils/logger.py`
- 顶部放可编辑常量：`START_PAGE`、`PAGE_COUNT`、`PAGE_SIZE`、`KEYWORD`、`UA`、`PAGE_URL`、`API_URL`
- 默认用 `requests`；**只有目标确实需要浏览器 TLS 指纹**或原案例已使用时才用 `curl_cffi.requests`
- `loguru` 可选：在 `utils/logger.py` 中封装 try loguru / PrintLogger，**不默认安装**
- 不添加 `logger.remove()` / `logger.add()`，不添加 `sys.stdout.reconfigure(...)`
- 主脚本用 `from utils.iv8_silent import import_iv8_silent` + `iv8 = import_iv8_silent()` **静默导入 iv8**
- 业务流程附近写短中文注释；终端打印完整响应
- **默认原样输出和保存逆向所需字段，不脱敏、不截断**（cookie / token / header / sign / URL / 请求体 / 响应字段 / telemetry）——只有用户明确要求脱敏时才处理
- 避免类、大型 wrapper 和未使用的通用能力

### 5.6 生成脚本流程（5 步）

1. 判断目标类型：签名 / JS challenge cookie / 浏览器 token / network hook signing / captcha-TDC / 带分页的组合
2. 读取最接近的 `references/cases/` 案例
3. 读 `script-writing-rules.md`，使用 `WORK_DIR = Path.cwd()` 和 `CACHE_DIR = WORK_DIR / "js_reverse_cache"` 规则
4. 需要 iv8 API 写法时读 `api-inventory.md`，按索引打开 `api-examples/` 下对应示例
5. 在当前工作目录写最小可运行主 `.py` + `utils/iv8_silent.py` + `utils/logger.py`

### 5.7 两类关键流程

**网络 Hook 签名（netLog 捕获）**
1. 在 iv8 中初始化目标 SDK / 保护 runtime
2. 在 iv8 内创建目标 XHR / fetch
3. 从 `iv8.netLog.entries` 读取最终 URL、headers、cookieHeader、body 元数据
4. 用 Python `requests` 发送捕获到的真实请求

**Trusted Input / TDC（滑块）**
1. Python 请求服务端 challenge / session 数据
2. 必要时 Python 计算图片缺口、PoW、轨迹
3. 用 `ctx.expose(...)` 暴露轨迹和常量
4. 用 `iv8.input.dispatchPointerEvent` / `dispatchMouseEvent` **派发可信事件**
5. 移动点之间推进逻辑时间
6. 读取目标 JS telemetry 后用 Python 提交

### 5.8 "案例回血"（自动回写）——视频重点宣传的自进化机制

> UP主原话：*"用这个 Skills 实现了某一个案例，它会自动地将这个案例回血到 Skills 当中……下一次再去立项同样的案例或同类型案例，它会自己去参考里面的案例，更快更有效率地产出。"*

- **仅在用户明确要求**"把本次成果沉淀为案例 / 回写到 skill / 新增 bundled case"时使用，默认交付脚本时不回写
- 回写前先完成普通任务链路，并尽量完成 `py_compile`、iv8 生成链路和真实请求状态码验证
- 回写规则：
  - 选择分类目录（`signatures/` / `js-challenges/` / `browser-tokens/` / `network-hook-signing/` / `captcha/`）
  - 用稳定短 slug 命名，如 `site-feature.py`
  - 复制已验证的最小可复用脚本到 `references/cases/<category>/<site-slug>.py`，**保留真实案例所需字段原文**
  - 只复制必要 frozen JS/HTML/小样本到 `references/cases/js_reverse_cache/<site-slug>/`
  - **不默认删除或截断**账号 Cookie、Authorization、个人 token、手机号等现场字段
  - 完整业务响应 JSON、运行报告或一次性抓包大文件**不默认入库**
  - 更新 `example-taxonomy.md` 的目录树、案例说明、素材列表和选择规则
  - 只有新增案例暴露了**通用写法**时，才更新 `script-writing-rules.md`（"不要为单站点细节污染通用规则"）

### 5.9 依赖与完成报告

```bash
# 核心依赖缺失时才安装
python -m pip install iv8 requests
# loguru 为可选依赖，除非用户明确要求，不安装
```

完成后简短报告须包含：脚本路径、`utils/iv8_silent.py` 与 `utils/logger.py` 路径、使用了哪个 bundled case 作为参考、哪些常量控制分页或请求输入、`js_reverse_cache/` 是否创建、动态 JS/临时 runtime/样本/报告的保存路径、（若回写）新增案例脚本与 taxonomy 更新位置、iv8 生成是否验证成功、**最终真实请求返回 200 还是实际状态码**、是否保存响应 JSON。

---

## 六、已实现案例库（11 个真实站点案例）

| 分类 | 案例文件 | 要点 |
|---|---|---|
| signatures | `jd-h5st.py` | **京东 h5st**：本地 HTML + 本地 JS bundle + MessageChannel patch + 真实请求 |
| signatures | `nmpa-md5-cookie.py` | 药监：MD5 header sign + challenge 页面 JS cookie |
| signatures | `pdd-anti-content.py` | **拼多多** PC 分类页 anti-content：动态下载当前 Next.js/webpack chunk，捕获 `__webpack_require__` 后调用内部混淆模块 |
| signatures | `xhs-homefeed.py` | **小红书** PC homefeed：webpack 模块导出 `signV2Init()`，iv8 中初始化 `window.mnsv2` 后生成 `X-s` / `X-S-Common` |
| js-challenges | `chinatax-ruishu.py` | 两阶段瑞数风格 cookie，iv8 内触发 XHR 捕获带签名/后缀 URL |
| js-challenges | `customs-ruishu.py` | 两阶段瑞数风格 cookie + 捕获 URL/header/cookie 后重放 |
| js-challenges | `ouyeel-202-cookie-url.py` | HTTP 202 challenge，内联/外链 JS，load 事件，netLog URL suffix，`document.cookie` |
| js-challenges | `cqvip-journal-search.py` | HTTP 412 challenge，iv8 生成 S/T cookie 后重放中文期刊搜索表单 POST |
| browser-tokens | `zhipin-stoken.py` | **BOSS直聘**：API 返回 seed/name/ts，iv8 计算 `__zp_stoken__` 后重试 |
| network-hook-signing | `douyin-bdms.py` | **抖音 BDMS / a_bogus** 风格 runtime，hook XHR 并改写 URL，从 netLog 读取最终 URL |
| captcha | `tencent-tdc-slider.py` | **腾讯 TDC**：可信 pointer/mouse 事件、PoW、collect / eks |

> UP主口播补充：*"由于时间原因只测试了这些案例……瑞数三四五六全部通杀，滑块系列也能实现，直聘也可以。"*
> SKILL.md 明确警告：**案例文件用于学习 API 和流程，不要盲目整站复制；必须替换当前目标站的 URL、headers、params、cookies、JS 入口和分页逻辑。**

---

## 七、后续规划（视频末尾）

作者正在自研一个 **MCP**（Model Context Protocol）服务，用于**接管魔改浏览器 / 指纹浏览器**。动机是：现在很多网站需要 AI 操作真实浏览器打开页面，但大量站点会检测自动化环境。通过 MCP 打开/操作魔改浏览器，可以覆盖更多"立项"需求。后续会更新到对应链接和网站中。

---

## 八、资料获取（画面信息）

视频 00:03–00:10 展示了网盘/企业版文件目录：

```
群组可见 /../【05】青木老师/爬虫逆向资料/
└── 06-skill-20260615/
    ├── 逆向skill.zip      （所有者：青木）
    ├── skill.zip          （所有者：海小）
    └── CloakBrowser.zip   （魔改/指纹浏览器）
```

同目录下还有：`05-小程序系列`、`01-爬虫逆向案例（长期-长视）`、`07-python-PyCharm新版本`、`04-基础系列课程`、`03-JS逆向`、`02-xx源码原理详解`。

---

## 九、完整字幕（Whisper-large-v3 转写，带时间戳）

```
[   0.00-   6.40] 最新版AI逆向Skills，主流大厂加密、瑞数、验证码系列都能通过这套Skills搞定，完整的Skills已经给大家准备好了。
[   8.85-  15.73] 今天给大家分享的是我们经过了5月份一整个月优化调试，然后在6月初落地的最新版本的逆向Skills。
[  15.95-  30.23] 那么这一套Skills里面包含了绝大部分的我们做Web端逆向的技能点，比如说补环境，然后去定位加密参数，以及追踪调用链的，JS逆向的，然后专门去做协议、对应的Cookie、WSM等等这一系列的技能点。
[  30.43-  43.87] 然后极验专项，腾讯滑块专项，V8补环境专项，以及通过MCP来控制浏览器，注入对应的一些HOOK脚本等等之类的，去追踪瑞数专项，还有专门去做WAF、Cookie专项的。
[  44.29-  55.65] 那么目前我们去分Skills就可以分成通用的以及这种专项的。通用的比如说这种补环境通用，然后追踪调用链通用，这种是通用的；然后专门去做某一件事情就算是专项的一些Skills。
[  55.99-  60.27] 我们目前在5月份花的时间最多的是在这个Skills上面。
[  60.41-  63.09] 这里可以给大家看一下它具体里面去做了什么事情。
[  63.73-  69.49] 整个它是生成一个紧凑可运行的Python脚本的，它是基于这个V8来去实现的。
[  69.57-  71.15] 那么这个V8是什么东西我们先来了解一下。
[  71.47-  78.45] 它其实就是通过Python去联动这个C++，内置了一个浏览器环境。
[  78.79-  84.87] 那么以前我们如果去补环境，需要去通过Node.js来去补，对不对，通过Node来去补上对应的环境。
[  85.03-  90.27] 那这个时候就需要去用一些比如说环境代理去吐出环境，
[  90.41-  92.81] 再去根据那个环境日志来去补上对应的环境。
[  93.09-  99.81] 但现在完全不需要去基于Node来去补了，可以直接用这个V8让它去执行对应的脚本。
[  99.91- 103.91] 它可以去自己调它内置的一些浏览器对应的接口来去实现。
[ 104.45- 108.65] 所以我们通过Node.js来去补环境的一个方式就算是过去式了。
[ 109.65- 114.81] 那么目前我们通过这个Skills能够去实现的一些案例，就是已经实现的案例，它还能去实现更多的案例。
[ 114.81- 119.23] 我们目前由于时间的原因就只是去测试了这些案例，比如说某东、某多多，
[ 120.45- 126.15] 某红书，然后瑞数，瑞数三四五六全部通杀，这个已经是通杀了的。
[ 126.69- 130.67] 包括这个滑块系列的，它也能够去实现。
[ 131.39- 133.79] 那个什么直聘的，它也可以去实现的。
[ 133.99- 140.27] 所以它能够去实现很多的一些案例，只要它是需要去补环境的，那么它都可以基于这样的Skills来去实现。
[ 140.83- 145.61] 那么这个Skills还有一个功能叫做自动回血功能，叫做案例回血功能。
[ 145.61- 149.59] 当我们用这个Skills它实现了某一个案例，
[ 149.77- 150.43] 它会自动的，
[ 150.45- 168.53] 去将这个案例回血到这个Skills当中。那么这个时候我们就不需要让它重新去生成了，而且你下一次再去用这个Skills的时候，再去立项同样的案例或者同类型的案例，它会自己去参考对应里面的一些案例，然后来去实现对应里面的一些逻辑，能够更快、更有效率地去产出目前的一个需求。
[ 168.77- 179.85] 所以这个是我们去加的一些规则，包括这里面什么依赖也好，它会自己去安装，对应的一些什么报告等等的，这个是可以让它出对应的一个分析报告的。
[ 180.70- 194.64] 然后在里面还会有很多的一些细节，它怎么去实现的，生成脚本的流程是什么什么什么，这些大家到时候可以去领取之后自行去看，好吧，我就不再去细讲了，它主要其实就是去做那个补环境来去实现的。
[ 195.36- 203.91] 在这里面它还会有对应的一些边界，就比如说做什么什么需求的时候，可以去交给另外的一些更适合的Skills来去实现。
[ 204.49- 210.37] 然后比如说这个诸如HOOK的时候就交给他，做滑块/极验交易的时候交给他等等，补环境的话要去用node，
[ 210.93- 220.83] 就交给他，所以这个时候我们就可以去让AI整个去调度这样的一个Skills，就这一整套Skills就会更加方便，然后AI也会更加智能一点。
[ 221.64- 240.98] 那么再给大家同步一下我们后续会去实现的一些东西，就是我们现在已经除了这种案例Skills之外，还在做一个事情叫做MCP，就是自己去做一个MCP，去接那种魔改浏览器或者指纹浏览器，就是说因为现在很多网站它需要去通过AI操作浏览器来去打开页面，
[ 241.12- 257.90] 但是很多网站会检测，对不对，所以我们现在在去实现的是这样的一个通过MCP来去打开或者操作魔改浏览器，来去实现更多的一些逆向需求。这个我们后续也会更新到对应的一个链接当中、网站当中，好吧，当然如果需要的话都可以来去领取的。
```

---

## 十、蒸馏说明与可信度

| 项目 | 说明 |
|---|---|
| 字幕来源 | 官方**无 CC 字幕**（播放器接口 `subtitles: []`），由 Whisper-large-v3 转写，技术术语已按上下文校正（如"MV8"→"V8"、"IST结混"→"JS逆向"、"MCEP"→"MCP"、"立项"→"逆向"） |
| 画面来源 | 480P（未登录画质上限）抽帧 110 张 → 差分去重 39 张 → PaddleOCR v5 mobile 提取 |
| 画面覆盖 | 00:00–00:10 技能清单界面、00:03–00:10 资料目录、01:02–03:42 SKILL.md 全文（186 行，已覆盖约 95%）、04:17 结尾 |
| 主要误差 | OCR 在 480P 下对中文长句有错字，已根据上下文与重复帧交叉校验修正；**技能名、案例路径、API 名等标识符已逐帧比对确认** |
| 外部补充 | `iv8` 的技术背景来自 PyPI 官方页与项目 README，非视频内容，已单独标注 |

**同目录附带**：`BV13nTj6JEWT_字幕.srt`（可直接挂字幕播放器）、`BV13nTj6JEWT_字幕.txt`（带秒数纯文本）
