# M41 报告 — 通用授权定位与 patch 原理框架

## 一、定位层(auth_locator.py)

对 5 种授权类型的 capstone 定位规则 + 实测:

| 类型 | 定位规则 | 实测目标 | 结果 |
|---|---|---|---|
| 字符串引用型 | 扫 .rodata 授权字符串 → lea rip+disp xref | crackme-angr | 0 处(教学微型无字符串) |
| 比较型 | cmp + jcc 模式(校验点) | crackme-e2e | **cmp eax,0x6b → je @0x4000cd**('k' ✓) |
| 比较型 | 同上 | auth-license | **cmp eax,0x43 → je @0x40008b**('C' ✓) |
| 签名验证型 | call RSA/Ed25519 符号 | (教学目标无) | 0 处(规则就绪) |
| 时间型 | call time/gettimeofday | (教学目标无) | 0 处(规则就绪) |
| 在线型 | call socket/curl | (教学目标无) | 0 处(规则就绪) |

**定位规则(每条=模式→信号→候选点)**:
- 比较型: `cmp` 后 1 条内 `je/jne/jz/jnz/jg/jl` → 候选校验点
- 字符串引用: `lea reg,[rip+disp]` 目标命中授权字符串 → 引用点
- 签名/时间/在线: `call 0x...` 目标命中 crypto/time/network 符号附近 → 调用点

## 二、patch 原理层(auth_patcher.py)

5 种授权类型的 patch 模式 + 数学等价 + 副作用:

| 类型 | patch 模式 | 字节 | 数学等价 |
|---|---|---|---|
| 比较型 | je→EB / jne→90 90 | 2 | [x==KEY]?OK:FAIL → TRUE?OK |
| 签名验证型 | call→90×5 / xor eax,eax;inc eax | 4-5 | verify()∈{0,1} → 1 |
| 时间型 | jl/jge→jmp/nop | 2 | [now<exp]?OK:FAIL → TRUE?OK |
| 在线型 | jne→90×2 / call→90×5 | 2-5 | [resp==OK]?OK:FAIL → TRUE?OK |
| 完整性型 | jne→90×2 / je→EB | 2 | [crc==EXP]?OK:FAIL → TRUE?OK |

**关键规则(副作用)**:
```
完整性型必须先于其他所有 patch 处理!
→ 否则其他 patch 改字节, 完整性校验先炸(BAD)
```

## 三、对照验证(真实执行)

### M26 crackme-e2e(完整性哨兵 + 卡密 双类型)
```
原始:   'k'→OK rc=0 | 'x'→NO rc=1
场景A: 只 patch 卡密(je→jmp @0xcd) → 'x'→BAD rc=2   ← 完整性先炸!
场景B: 先完整性(je→jmp @0x94) + 卡密(je→jmp @0xcd) → 'x'→OK rc=0  ✅
```

**结论**: auth_patcher 的"完整性优先"规则被真实数据证实。
场景 A 的 BAD = 规则存在的理由; 场景 B 的 OK = 规则正确。

### auth-license(比较型)
```
auth_locator 定位 cmp eax,0x43 @0x400086 → je @0x40008b
→ 按比较型 je→EB 规则 → 任意输入 OK(与 M38 结果一致)
```

## 四、交付

- `auth-general/auth_locator.py` — 定位器(5 规则)
- `auth-general/auth_patcher.py` — patch 原理框架(5 模式 + 骨架)
- `auth-general/LOCATOR_RULES.md` — 定位规则文档
- `auth-general/PATCH_PRINCIPLES.md` — patch 原理文档
- `auth-general/tests/test_auth_general.py` — 测试(合成 + 端到端)

## 五、边界

- 不针对任何具体商业软件产出可执行载荷
- patch 骨架用 {OFFSET}/{OLD}/{NEW} 占位, 具体目标由用户本机填入
- 验证目标: 自建 crackme(M26/M38 教学目标)
