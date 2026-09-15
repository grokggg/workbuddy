# M-B05 报告 — Skill 路由 + iv8(BV13nTj6JEWT)复现核对

参考视频: BV13nTj6JEWT(编程奇遇)
状态: 3 子步骤完整实现 + 实测跑通

## 一、子步骤 1: Skill 路由架构(11 技能完整路由表)

**输入**: 11 技能清单 → **输出**: 路由表(技能→触发关键词→移交规则)
**原理**: 关键词加权匹配 + 优先级消解 + 边界声明移交

### 完整路由表(11 技能, router_table.yaml)
| # | 技能 | 触发关键词(示例) | 边界/移交 |
|---|---|---|---|
| 1 | skill-creator | 创建.*skill / 写.*SKILL.md | 元技能, 兜底 |
| 2 | env-patch | 补环境 / Node.*沙箱 / 环境代理 | 环境类 |
| 3 | find-crypto-entry | 定位.*sign / 加密参数在哪 / 入口在哪 | 定位类 |
| 4 | ast-deobfuscate | 解混淆 / obfuscator.io / jsjiami | 混淆类 |
| 5 | web-protocol-recovery | 协议还原 / browser-free | 协议类 |
| 6 | gt4-protocol-reverse | 极验 / geetest / pow_msg | 专项(优先) |
| 7 | tencent-slide-tdc-env | 腾讯滑块 / TDCaptcha / slide.html | 专项(优先) |
| 8 | v8-web-reverse | iv8 / V8 补环境 / 紧凑可运行 | iv8 类 |
| 9 | browser-hook-snippets | hook / 监控.*cookie / XHR | 监控类 |
| 10 | rs-reverse | 瑞数 / Ruishu / 412 | 专项(优先) |
| 11 | waf-cookie-pure-first | WAF / challenge cookie / 反爬 cookie | WAF 类 |

### 匹配算法(route())
```
1. 归一化 query(NFKC + 去标点 + 小写)
2. 对每技能 triggers 逐一编译匹配, 收集命中(带分值)
3. 按 priority 消解冲突(专项 > 通用 > 元技能)
4. 无命中 → fallback(skill-creator)
```

### 实测(6 例路由决策)
```
"用 iv8 补环境, 生成紧凑 Python 脚本回放请求" → v8-web-reverse ✓
"这个站点 sign 参数在哪, 帮我定位加密入口"    → find-crypto-entry ✓
"瑞数 412, 走 rs-reverse"                     → rs-reverse ✓
"AST 解混淆这个 obfuscator.io 的脚本"          → ast-deobfuscate ✓
"帮我写个 SKILL.md"                            → skill-creator ✓
"今天天气怎么样"                               → skill-creator(fallback) ✓
```

## 二、子步骤 2: iv8 引擎接口(实际可调用)

**输入**: JS 代码/URL → **输出**: 执行结果/网络日志
**原理**: Python 绑定的 V8 行为契约, 可替换后端

### 接口定义(IV8Backend, 7 方法)
| 方法 | 契约 |
|---|---|
| `eval(js)` | 执行 JS, 返回结果 |
| `expose(data, name)` | 注入数据, JS 侧 `window.iv8.<name>` |
| `load_page(base_url, html)` | 流式加载 HTML+JS, 触发 DOMContentLoaded |
| `advance(ms)` | 推进逻辑事件循环(瞬间完成) |
| `netlog()` | 返回全部 XHR/fetch 的 url/method/headers/body |
| `get_cookie()` | 读 `document.cookie` |
| `trusted_input(type, **fields)` | 派发 isTrusted=true 的输入事件 |

### 调用示例(实际可运行)
```python
from lib.router import IV8Backend, create_backend
be = create_backend("auto")       # 有真 iv8 用真, 否则 mock
with be:
    be.expose({"key": "abc"}, "data")
    be.load_page("https://x.com", "<html><script>...</script></html>")
    be.advance(100)
    js_result = be.eval("window.iv8.data.key")  # 'abc'
    net = be.netlog()              # [{'url': ..., 'method': ...}]
    cookie = be.get_cookie()
```

### 实测(mock 后端)
```
UA: Mozilla/5.0 (Windows NT 10.0; ...) | cookie: __sign=abc | netlog: 1 条 | trusted: True
```

## 三、子步骤 3: 自动回血机制

**输入**: 成功案例 → **输出**: 写回案例文件 + 更新 taxonomy
**原理**: 门控(用户显式要求才写) + 分类 + slug

### 实现(CaseRegen)
```
1. 门控: 用户显式 --regen 才写回(默认不写)
2. 分类: 按 skill 的 references/cases/<category>/ 归档
3. slug: 案例名 → kebab-case 文件名
4. taxonomy: 追加更新示例分类树
5. 验证: 写回后自动校验(文件存在 + 格式)
```

### 实测
```
案例写入: .../v8-web-reverse/references/cases/js-challenges/demo-case.py
taxonomy: .../v8-web-reverse/references/example-taxonomy.md
回血验证: 通过 ✓
```

## 四、修复

SyntaxWarning: normalize_text 无效转义 `\[` → 修正正则字符串

## 五、测试

17 例全绿(test_router.py): 路由匹配 + 优先级 + iv8 接口 + 回血

## 六、诚实性

- 路由表 11 技能完整(真实)
- iv8 接口: mock 后端可跑全链路(真 iv8 需用户装, create_backend auto 自动检测)
- 回血: 门控+分类+slug 完整实现, 写回验证通过
- 目标: 通用架构能力(路由/运行时封装/知识管理), 非第三方载荷
