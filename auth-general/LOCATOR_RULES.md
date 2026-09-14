# 定位规则文档 — 通用授权函数定位

## 方法: 模式 → 信号 → 候选点

每条规则 = 反汇编模式 + 信号提取 + 候选点输出(不自动 patch)。

---

## 1. 字符串引用型

**适用**: 授权结果提示(OK/NO/expired)、错误消息(license.txt 引用)

```
模式: lea reg, [rip + disp]   ; 加载字符串地址
信号: disp 计算的目标 ∈ .rodata 授权字符串集合
候选点: lea 指令地址
```

**capstone 扫描**:
```python
for insn in md.disasm(code, base):
    if insn.mnemonic in ("lea", "mov") and "rip" in insn.op_str:
        disp = extract_rip_disp(insn.op_str)
        target = insn.address + len(insn.bytes) + disp
        if target in auth_string_set:
            emit(insn.address, target, string)
```

**验证**: 用 M28 crackme-angr —— 教学微型二进制无 .rodata 授权字符串
(0 命中 = 真实), 商业软件(WinRAR)字符串剥离(0 命中 = 识别成功)

---

## 2. 比较型

**适用**: 卡密/序列号/激活码直接比较

```
模式: cmp reg, imm 或 cmp [mem], reg
信号: cmp 后 1~6 条内出现 jcc(je/jne/jz/jnz/jg/jl/jge/jle)
候选点: cmp 地址 + jcc 地址
```

**capstone 扫描**:
```python
prev = None
for insn in md.disasm(code, base):
    if prev and prev.mnemonic == "cmp" and insn.mnemonic in JCC_SET:
        emit(prev.address, prev.op_str, insn.address, insn.mnemonic)
    prev = insn
```

**验证**: M26 crackme-e2e → `cmp eax,0x6b; je` @0x4000cd('k' 命中)
M38 auth-license → `cmp eax,0x43; je` @0x40008b('C' 命中)

---

## 3. 签名验证型

**适用**: RSA/Ed25519 签名 token(如 grantmint、Sublime)

```
模式: call <crypto_fn> ; test eax,eax ; jcc
信号: call 目标 ∈ {RSA_verify, ED25519, EVP_DigestVerify, crypto_sign} 导入附近
候选点: call 地址(验证调用)
```

**capstone 扫描**:
```python
for insn in md.disasm(code, base):
    if insn.mnemonic == "call" and insn.op_str.startswith("0x"):
        tgt = int(insn.op_str, 16)
        if any(abs(tgt - sym_va) < 0x100 for sym_va in crypto_syms):
            emit(insn.address, "call", tgt)
```

**验证**: M39 grantmint 协议分析(Ed25519 verify 调用在服务端库,
客户端只有公钥——教学上无独立二进制可测, 规则就绪)

---

## 4. 时间型

**适用**: 试用期/过期检查

```
模式: call time/gettimeofday/clock_gettime → 计算差值 → cmp → jcc
信号: call 目标 ∈ time 系导入附近
候选点: 时间比较 jcc(在 call 后 20 条内)
```

**capstone 扫描**:
```python
time_call_addr = None
for insn in md.disasm(code, base):
    if insn.mnemonic == "call" and target_near(time_syms, insn):
        time_call_addr = insn.address
    if time_call_addr and insn.mnemonic in JCC_SET \
            and insn.address - time_call_addr < 20 * 16:
        emit(insn.address, "time-jcc")
```

---

## 5. 在线型

**适用**: 网络激活/服务器验证

```
模式: call socket/connect/send/recv/curl → 返回码 cmp → jcc
信号: call 目标 ∈ network 导入附近
候选点: 响应检查 jcc(call 后 20 条内)
```

**capstone 扫描**: 同时间型, 换成 net_syms(socket/connect/curl_easy)

---

## 通用流程

```
auth_locator.py <ELF>
→ string_refs: 授权字符串引用点
→ cmp_jcc: 校验点候选(最常见)
→ crypto_calls / time_calls / network_calls: 复杂类型
→ 用户对候选点人工确认 → 填 auth_patcher 骨架
```
