# M29 报告 — 带保护真实 crackme 批量处理

## 一、目标(4 个带保护 crackme)

| 目标 | 保护 | 原始大小 | 说明 |
|---|---|---|---|
| cm-upx1 | UPX -1 加壳 | 6,744 B | 压缩 26% |
| cm-upx6 | UPX -6 加壳 | 6,180 B | 压缩 24% |
| cm-upx9 | UPX -9 加壳 | 6,112 B | 最强压缩 |
| cm-base | 单校验点 | 17,080 B | M28 真实 crackme 原版 |

基类: reversinghub/crackme-angr-elf 预编译真实 ELF(17KB, strcmp 卡密校验)

## 二、工具链流程(process_real.py)

对每个目标:
1. **recon_v3 分析**(含 capstone 反汇编)
2. **保护识别**: 加壳目标节表 0 个/导入 0 个/入口是 UPX stub → 判定"加壳(UPX)"
3. **脱壳**: `upx -d`(带壳目标)
4. **capstone 定位校验点**: 反汇编 main → 找 `call 0x1050`(strcmp)→ 后续 `jne`
5. **patch**: jne -> NOP NOP
6. **验证**: 任意输入 -> "Congratulations!"

### 关键调试(F18: strcmp 后隔 test)
```
call 0x1050(strcmp) @ 0x1210
test eax, eax          ← 间隔指令(不是紧邻 jne)
jne 0x1227 @ 0x1217    ← 真正的校验分支
```
修复: patch 逻辑找 call 后 **6 条内**的条件跳转(跳过 test/cmp)。

### 关键调试(F19: main 定位边界)
入口反汇编取 32 字节时, `lea rdi` 指令跨边界被截断 → 取 64 字节修复。

## 三、批量结果(全真实执行)

| 目标 | 脱壳 | patch 点 | 破解验证 | 状态 |
|---|---|---|---|---|
| cm-upx1 | ✅ upx -d | 0x1217 jne→NOP | abc → Congratulations | ✅ |
| cm-upx6 | ✅ upx -d | 0x1217 jne→NOP | abc → Congratulations | ✅ |
| cm-upx9 | ✅ upx -d | 0x1217 jne→NOP | abc → Congratulations | ✅ |
| cm-base | - | 0x1217 jne→NOP | abc → Congratulations | ✅ |

**破解率: 4/4(100%, 诚实数据)**

## 四、文件

- `cm-upx1` / `cm-upx6` / `cm-upx9` — 3 个加壳目标
- `cm-base` — 原版
- `cm-*-unpacked` — 脱壳版
- `cm-*-cracked` — 4 个破解版
- `process_real.py` — 批量处理脚本(自动工具链)
- `M29_REPORT.md` — 本报告

## 五、意义

M29 首次处理**带保护的真实 crackme**(UPX 壳 × 3):
- 壳识别(recon_v3: 节表/导入归零 + 入口 stub)
- 脱壳(upx -d 真实执行)
- 校验点定位(capstone 反汇编 main + strcmp 交叉引用)
- 批量破解(process_real.py 全自动, 4/4)
