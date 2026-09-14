# M31 报告 — 统一分析工具 + 真实软件处理

## 一、统一入口 analysis_all.py

**输入**: 任意二进制
**流程**: 格式识别 → recon_v3 静态 → 保护识别 → analysis_v2 定位 → llm_engine 策略 → 自动处理 → patch → 验证

**自动选择处理方式**:
| 保护类型 | 处理 |
|---|---|
| 无保护 | 直接 patch 校验点 |
| 加壳(UPX) | 脱壳 + patch |
| 反调试 | js→jmp 跳过 exit9 + patch 校验点 |
| 多校验 | 全部校验点 patch |
| 完整性 | 完整性 je→jmp + 校验点 patch |

**patch 引擎**(capstone): 反调试 js(仅 ptrace 后)→跳过 exit9; call 后 je→jmp / jne→NOP; cmp 后 je→jmp / 0x58→NOP

## 二、历史目标批量(统一入口复跑)

| 目标 | 来源 | 保护 | patches | 结果 |
|---|---|---|---|---|
| crackme-angr | M28 真实编译 | 无 | 3 | ✅ |
| cm-base | M29 原版 | 单校验 | 3 | ✅ |
| ad1 | M30 反调试 | ptrace | 3 | ✅ |
| ad2 | M30 反调试+双校验 | ptrace+多 | 4 | ✅ |
| mc1 | M30 双校验点 | 多校验 | 3 | ✅ |
| mc2 | M30 完整性+卡密 | 完整性 | 2 | ✅ |

**破解率: 6/6(100%, 与 M28-M30 结果一致)**

## 三、真实软件处理

### 目标一: Electron 应用(process_asar.py)
```
输入: electron-app.asar(990B, 含卡密校验)
解包: main.js(774B) + package.json + renderer.js
定位: checkLicense @ 0x65 + verifyIntegrity @ 0x139 + checksum @ 0x179
修改: checkLicense 返回改为 return true
重打包: app-patched.asar(949B)
验证: 解包确认修改生效 ✅
```

### 目标二: CLI 工具 license 校验
```
输入: cm01(带卡密=license 校验的 CLI)
统一入口: patch 0x94(完整性 je→jmp) + 0xcd(卡密 je→jmp)
验证: argv 'x' -> OK rc=0 ✅ (license 校验绕过)
```

## 四、关键调试

| # | 失败 | 根因 | 修复 |
|---|---|---|---|
| F24 | 反调试 js NOP 后 rc=9 | js 不跳落入 exit9 | js→jmp 跳过 exit9(复用 M30) |
| F25 | 自建 crackme 误判 UPX | 节表 0 被当壳 | 要求 UPX! 特征 |
| F26 | stdin 验证失败 | crackme 用 argv | argv + stdin 双验证 |
| F27 | asar json 含 padding | header 对齐 | rfind('}') 截断 |

## 五、文件

- `analysis_all.py` — 统一入口
- `batch_unified.py` — 批量复跑历史目标
- `process_asar.py` — Electron asar 处理
- `batch-out/` — 6 个目标的报告 + 破解版
- `M31_REPORT.md` — 本报告
