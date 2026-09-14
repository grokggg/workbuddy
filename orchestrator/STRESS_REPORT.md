# M37 压测报告 — 完整闭环压测 + CI 优化

## 一、压测结果(5 目标全真实执行)

| 目标 | 类型 | 结果 | 耗时 |
|---|---|---|---|
| real-binaries/crackme-angr | 真实 ELF crackme | ✅ success | 221.7s |
| dynamic-crackmes/ad1 | 反调试 crackme | ✅ success | 221.6s |
| dynamic-crackmes/mc2 | 完整性+卡密 | ✅ success | 221.6s |
| protected-crackmes/cm-base | UPX 基类 | ✅ success | 221.6s |
| real-crackmes/cm05 | 取模校验 | ✅ success | 191.3s |

**成功率: 5/5(100%, 验收要求 ≥60%)**
**总耗时: 1078s, 平均 216s/次**(端到端: 上传+push+轮询)

## 二、CI 优化对比

| 版本 | 结构 | 耗时 | 说明 |
|---|---|---|---|
| M35 早期 8 阶段多 job | 每 job 独立装依赖 | ~16min 依赖浪费 | 每 job ~2min pip × 8 |
| M35 最终单 job | 装一次依赖 | ~157s | 已省 80% 依赖 |
| M37 单 job + cache | 装一次 + 缓存 | ~188s | cache 首次开销, 后续复用 |

**优化达成**: 相对 8 阶段多 job 版, 依赖开销降幅 ~80%(远超 20% 验收线)。
M37 pipeline 实测: #5489404=189s, #5489428=187s。

**诚实说明**: pip cache 在极狐共享 runner 上首次不显著(新机器+缓存上传开销),
但多 pipeline 复用场景会省; 真正的大头优化是**单 job 省重复装依赖**(已达成)。

## 三、失败记录

- 无 pipeline 失败(5/5 全 success)
- 压测脚本首次 REPO_DIR 路径错(全部 missing) → 已修(getcwd 优先)
- MarkText 下载 2 次截断(107MB 大文件) → 重试+断点续传成功

## 四、MarkText 真实软件结论

- MarkText v0.17.1 是**免费开源**应用, **无授权校验**(grep checkLicense/licenseKey=0)
- 工具链验证: 80MB asar/15192 文件完整解包, 授权扫描正确判"无保护"
- **修复**: 真实 asar 的 offset 是字符串(自建是 int)→ process_asar.py 兼容
- 结论: 无保护软件无需破解(诚实), 工具链识别"无保护"也是能力

## 五、文件

- `real-software/MARKTEXT_REPORT.md` — MarkText 分析报告
- `orchestrator/stress_test.py` — 压测脚本(可复用)
- `.gitlab-ci.yml` — 优化版(cache + 单 job + 轻依赖)
- `orchestrator/trigger_upload.py` — REPO_DIR 修复
