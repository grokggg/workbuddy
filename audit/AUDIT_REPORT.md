# AUDIT_REPORT — 路线 B 真实性审计(M-B10)

日期: 2026-09-14

## 审计表

| 模块 | 声称状态 | 验证方式 | 端到端跑过? | 占位符残留? | 未暴露 bug? | 判定 |
|---|---|---|---|---|---|---|
| v1 四模型控制台 | ✅ 完成 | 单元+端到端 | ✅ console --backend mock | 无 | 无 | ✅ 通过 |
| v2 冷咖啡 | ✅ 完成(补件) | 单元+端到端 | ✅ run-full 11/12 | **修复前: 代码真占位** | **2 个**(手动解包偏移+rc键) | ✅ 修复后通过 |
| v3 五步法 | ✅ 完成 | 单元+端到端 | ✅ five-step 5/5 | **修复前: 代码真占位** | **1 个**(step_modify 用错属性) | ✅ 修复后通过 |
| v4 越狱泄露 | ✅ 完成 | 单元+端到端 | ✅ all 7/8 | 无 | 无 | ✅ 通过 |
| v5 AI 改跳转 | ✅ 完成 | 单元+端到端 | ✅ analyze | 无 | 无(头误判已修 M-B04) | ✅ 通过 |
| v6 Skill 路由 | ✅ 完成 | 单元+端到端 | ✅ demo | 无(REFERENCE_LAYER 是文档模板) | 无 | ✅ 通过 |
| 评论区 5 能力 | ✅ 完成 | 单元+端到端 | ✅ 统一入口 | 无(模板参数占位=合理) | 无 | ✅ 通过 |
| 总集成 | ✅ 完成 | 单元+端到端 | ✅ stress 11/11 | 无 | 无 | ✅ 通过 |

## 发现清单

### 占位符残留(审计前 2 处真占位, 已修)
1. **v2 runner_full.py 段 10-12**: `{PATCH}`/`{COMMAND}`/`{VERIFY_CMD}` + placeholder=True
   → 已修为真实执行(sed patch / asar_pack / node verify), 实测 11/12(段4=环境依赖)
2. **v3 engine.py 步 4-5**: `{PATCH}`/`{VERIFY_CMD}` + placeholder=True
   → 已修为真实字节 patch + 运行对比, 实测 5/5

文档说明(非真占位): v6 REFERENCE_LAYER.md(格式模板, 有 FILLED 对照)、
01-agents-md(模板参数)、asar_inspect.js(技术注释)。

### 措辞红线命中(0 处)
全仓搜"中性化/机制研究/模拟/等价物/自建"——命中均为**性质判定**:
v1"自建 HTTP"(实现方式)、v4"模拟响应"(MockLLM 靶场注释)、v2"自建 asar"(教学目标标注)。
无"中性化/占位符包装回避"。

### 恒真断言(0 处)
抽查 v1/v3/v4/v6/5能力/集成测试: 无 assert True/1==1/pass。断言均为真实判定。

### 未暴露 bug(3 处, 全部当场修复)
1. **v2 runner_full 手动解包偏移错误**: json 从 8 读(标准 asar 在 16) + offset 未加数据区基准
   → 修: 兼容双格式(8B 头简化 / 16B 头标准), offset 相对/绝对自适应
2. **v2 runner_full stage_patch/verify 用 rc['rc']**: _run 返回 exit 非 rc
   → 修: 用 rc['exit'] + stdout
3. **v3 engine step_modify 用 self.target**: 实际属性 self.target_root
   → 修: 统一 target_root + CLI 加 --patch

## 修复验证

```
v2 run-full(教学 asar): 11/12
  段7 纯Python解包 OK / 段8 结构 OK / 段9 卡密定位 OK
  段10 sed patch rc=0 / 段11 asar_pack 360B / 段12 node LICENSE_OK rc=0
  段4 FAIL = @electron/asar 缺失(环境 Node 20.19<22, 非代码问题)

v3 five-step(教学 ELF --patch 8b eb 74): 5/5
  步4 字节 patch 完成(74→eb) / 步5 原始 rc=1 NO → patch后 rc=0 OK

v2 test_runner_full: 10 例全绿(原 6 失败已修)
v3 test_engine: 18 例全绿(原 3 失败已修)
```

## 审计结论

**有条件通过** — 条件已满足:
- 占位符: v2/v3 代码真占位已修复为真实执行(教学/自有目标), 实测通过
- 未暴露 bug: 3 处当场修复 + 测试更新全绿
- 措辞: 0 红线命中(全部性质判定)
- 恒真断言: 0 处
- 封版有效性: tag v3.0-routeB-final 内容需随本审计修复更新(重打 tag)

## 修复建议(已执行)

1. 提交 v2/v3 修复 + 测试更新, 重推双远端 + 重打 tag
2. 审计报告入仓 audit/AUDIT_REPORT.md
