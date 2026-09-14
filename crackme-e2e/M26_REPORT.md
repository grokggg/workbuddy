# M26 报告 — 端到端 Crackme 实战闭环

## 一、Crackme 构造

**目标**: 教学级 crackme(纯 Python 构造 ELF x86-64, 无编译器环境)

**特性**:
1. **卡密校验**: argv[1] 首字符 == 'k'(0x6B) 才 OK
2. **完整性校验**: 运行时对卡密校验代码区(cmp+je, 7 字节)求和, 对比预置值
   —— 任何 patch 卡密指令都会改变校验和 → BAD/exit 2

**文件**:
- `build_crackme.py` — 构造器(机器码 + ELF 打包)
- `crackme` — 原始二进制(286 B)
- `simulate.py` / `ptrace_step.py` — 调试辅助

## 二、原始行为验证

| 输入 | 输出 | exit |
|---|---|---|
| `./crackme k` | OK | 0 |
| `./crackme x` | NO | 1 |
| `./crackme`(无参) | NO | 1 |

## 三、工具链分析

### recon_v2
```
格式: ELF | 架构: x64 | 类型: EXEC
加壳: 未见壳特征 (熵均值 3.26)
完整性校验: 未检测到  ← 盲区: 行为型校验无字符串特征
```
**失败点 F15**: recon_v2 检不出行为型完整性校验(无 checksum/md5 字符串)。
修复方向: 增强检测"cmp 累加和对比"模式。

### analysis_v2(M26 增强后)
```
校验模式: 3 处
  0x8f [cmp-imm32] 3d 40 00 00 00 74 24   ← 完整性校验 cmp
  0xc8 [cmp-imm32] 3d 6b 00 00 00 74 24   ← 卡密比较 cmp
  0xc5 [movzx+cmp(卡密)] 0f b6 00 3d 6b   ← 卡密校验定位
```
**增强**: 新增 `cmp-imm32` + `movzx+cmp(卡密)` 模式, 准确定位卡密比较指令。

## 四、破解闭环(真实执行)

### 步骤 1: patch 卡密分支(je → jmp)
```
偏移 0xcd: 74 24 (je +36) → EB 24 (jmp +36)
```
结果: **BAD / exit 2** —— 完整性校验拦截! (patch 卡密改变了校验区字节和)

### 步骤 2: patch 完整性校验(je → jmp)
```
偏移 0x94: 74 24 → EB 24 (无条件跳 integrity_ok)
```
结果: **OK / exit 0** —— 双 patch 破解成功!

### 验证日志
```
原版:    ./crackme k  -> OK(0)    ./crackme x -> NO(1)
patch1:  ./crackme-patched x -> BAD(2)   ← 完整性拦截
patch2:  ./crackme-cracked x  -> OK(0)   ← 破解成功
```

## 五、补丁脚本

```python
#!/usr/bin/env python3
# crackme_e2e_patch.py — 完整破解(占位符版)
import sys

def patch(path):
    d = bytearray(open(path, 'rb').read())
    # 1. 卡密 je -> jmp (0xcd)
    d[0xcd] = 0xEB
    # 2. 完整性 je -> jmp (0x94)
    d[0x94] = 0xEB
    out = path + '.cracked'
    open(out, 'wb').write(d)
    os.chmod(out, 0o755)
    return out

if __name__ == '__main__':
    out = patch(sys.argv[1])
    print(f'破解版: {out}')
```

## 六、失败点与教训

| # | 失败 | 根因 | 修复 |
|---|---|---|---|
| F15 | recon 检不出行为型完整性 | 无字符串特征 | analysis_v2 增强(cmp 模式) |
| F16 | 手写机器码跳转偏移错误 | jnz 目标算错 1 字节 | ptrace 单步定位(死循环) |
| F17 | ptrace 单步卡死 | SINGLESTEP 在循环处不停 | 分析 RIP 变化定位 |

**教训**: 行为型保护(运行时求和校验)需要**动态分析**或**指令模式识别**,
纯字符串特征检测必然漏。这是工具链的真实盲区, 已通过 analysis_v2 增强缓解。

## 七、交付

- crackme(原始) + crackme-patched + crackme-cracked(破解版)
- build_crackme.py(构造器) + patch 脚本
- 验证日志 + 报告
