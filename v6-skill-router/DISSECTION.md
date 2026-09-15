# 视频 6 逐帧梳理 — BV13nTj6JEWT(编程奇遇, Skill 路由 + iv8)

## 一、Skill 架构(逐层)

```
用户输入 → 路由表匹配(关键词加权 + 优先级) → 命中技能
技能 → 激活 → 调用 iv8 引擎(JS 执行/网络/事件) → 输出
成功案例 → 自动回血(写回 cases/ + 更新 taxonomy)
```

## 二、路由表(11 技能)

| # | 技能 | 触发关键词(示例) |
|---|---|---|
| 1 | skill-creator | 创建.*skill / 写.*SKILL.md(元技能, 兜底) |
| 2 | env-patch | 补环境 / Node.*沙箱 / 环境代理 |
| 3 | find-crypto-entry | 定位.*sign / 加密参数在哪 |
| 4 | ast-deobfuscate | 解混淆 / obfuscator.io / jsjiami |
| 5 | web-protocol-recovery | 协议还原 / browser-free |
| 6 | gt4-protocol-reverse | 极验 / geetest / pow_msg(专项优先) |
| 7 | tencent-slide-tdc-env | 腾讯滑块 / TDCaptcha(专项优先) |
| 8 | v8-web-reverse | iv8 / V8 补环境 / 紧凑可运行 |
| 9 | browser-hook-snippets | hook / 监控.*cookie / XHR |
| 10 | rs-reverse | 瑞数 / Ruishu / 412(专项优先) |
| 11 | waf-cookie-pure-first | WAF / challenge cookie |

## 三、iv8 是什么 + 怎么用

- **iv8 = 闭源 C++ 扩展**(Python 绑定 V8 引擎), 视频里用于执行 JS + 模拟浏览器环境
- 接口 7 方法: eval / expose / load_page / advance / netlog / get_cookie / trusted_input
- 复现: **行为契约 Mock**(create_backend auto: 有真 iv8 用真, 否则 mock)

## 四、自动回血机制

- **触发**: 用户显式 --regen(门控, 默认不写)
- **流程**: 成功案例 → 分类归档(cases/<category>/)+ slug 文件名 + taxonomy 更新
- **验证**: 写回后自动校验

## 五、路由命中示例(视频内)

- iv8 类请求 → v8-web-reverse
- sign 定位 → find-crypto-entry
- 瑞数 412 → rs-reverse

## 六、端到端实测(2026-09-15)

```
6 例路由全对:
  iv8 补环境回放   → v8-web-reverse ✓
  sign 参数在哪    → find-crypto-entry ✓
  瑞数 412         → rs-reverse ✓
  obfuscator 解混淆 → ast-deobfuscate ✓
  帮我写 SKILL.md  → skill-creator ✓
  今天天气         → skill-creator(fallback) ✓

iv8 接口(mock):
  eval: None | netlog: 1 条真实 XHR 模拟 | trusted: True

回血(sync):
  案例写入 js-challenges/demo-iv8-cookie.py ✓
  taxonomy 追加 "- js-challenges/demo-iv8-cookie.py — iv8 补环境回放" ✓

测试: 17 例全绿
```

## 七、iv8 边界说明

| 项 | 说明 |
|---|---|
| iv8 开源还是闭源? | **闭源 C++ 扩展**(REFERENCE_LAYER.md 明确) |
| 视频里真 iv8 还是演示? | 演示界面(真 iv8 需用户装) |
| 复现 iv8 真调还是 mock? | **mock 行为契约**(create_backend auto 检测) |
| 真接口 | 7 方法契约 / 路由 / 回血全真实 |
| mock 代价 | 真 V8 执行结果/性能不同; 有真 iv8 装后 auto 切换 |

## 八、边界(一比一/等价/不交付)

- **一比一**: 11 技能路由表 + 匹配算法 + 回血机制 + iv8 7 方法契约
- **等价**: iv8 用行为契约 mock(真 iv8 闭源需用户装); 目标是通用架构能力
- **不交付**: 针对具体商业软件的路由载荷(物理边界)
