# Patch 原理文档 — 通用授权 patch 模式

## 核心原则

1. **最小 patch**: 尽量 2 字节(jcc 改向), 不重写逻辑
2. **完整性优先**: 有完整性校验必须先处理它, 否则其他 patch 触发自校验
3. **数学等价**: patch 后逻辑必须与"正确输入"行为一致(恒真/恒真路径)

---

## 1. 比较型: je→jmp / jne→nop

```
原始: cmp eax, KEY
      je  OK      ; eax==KEY → OK
      jmp FAIL
patch: je → EB rel8(恒跳 OK)
数学:  [input==KEY]?OK:FAIL  →  TRUE?OK
副作用: 若 cmp 字节被完整性校验覆盖 → 触发自校验(需先处理完整性)
字节: 2(je→EB 同偏移)
```

---

## 2. 签名验证型: call→nop×5

```
原始: call verify_token  ; rax = verify(sig, key) ∈ {0,1}
      test eax, eax
      jz FAIL             ; rax==0 → 失败
patch: call → 90 90 90 90 90(跳过验证)
       或 test 后 jz→jmp
数学:  verify()∈{0,1} → 1(恒真)
副作用: 后续可能再解 token 字段(多处校验) → 需多处 patch
字节: 5(call) 或 4(xor eax,eax; inc eax)
```

---

## 3. 时间型: 时间比较 jcc 恒真

```
原始: call time()
      cmp/sub 计算剩余
      jl OK / jge FAIL   ; now < expiry?
patch: jl → jmp(恒 OK) 或 jge → nop(不跳 FAIL)
数学:  [now<exp]?OK:FAIL → TRUE?OK
副作用: expiry 相关日志/计数状态不一致(无害于功能)
字节: 2
```

---

## 4. 在线型: 返回码比较恒真

```
原始: call http_verify
      cmp eax, OK_CODE
      jne FAIL           ; resp != OK → 失败
patch: jne → 90 90(不跳 FAIL)
       或 call → 90×5(跳过网络调用, rax 残留)
数学:  [resp==OK]?OK:FAIL → TRUE?OK
副作用: 服务端无授权记录(仅离线显示 OK)——真正的服务器验证在他人服务,
       不在本框架范围
字节: 2(比较) 或 5(跳调用)
```

---

## 5. 完整性型: 校验比较恒真

```
原始: call checksum(self)
      cmp eax, EXPECTED
      jne FAIL           ; 自修改 → 校验失败
patch: jne → 90 90(不跳 FAIL)
数学:  [crc==EXP]?OK:FAIL → TRUE?OK
副作用: **必须最先处理**——否则其他 patch 改字节 → 本校验先炸(BAD)
字节: 2
```

---

## 实战验证(M26 crackme-e2e 双类型)

```
目标: 完整性哨兵 + 卡密校验(两个校验点)

场景 A(错误顺序): 只 patch 卡密 je→jmp @0xcd
  结果: 'x' → BAD rc=2   ← 完整性先炸! 证明"完整性优先"规则

场景 B(正确顺序): 先完整性 je→jmp @0x94, 再卡密 je→jmp @0xcd
  结果: 'x' → OK rc=0   ← 完整绕过成功

结论: patch 顺序 = 完整性 → 其他(先处理会因改字节而触发的检查)
```

---

## 补丁脚本骨架(占位符)

auth_patcher.py --skeleton 输出:
```python
PATCHES = [
    {"offset": {OFFSET}, "old": bytes.fromhex("{OLD}"),
     "new": bytes.fromhex("{NEW}")},
]
# {OFFSET}/{OLD}/{NEW} 由用户对合法目标用 auth_locator 定位后填入
```
