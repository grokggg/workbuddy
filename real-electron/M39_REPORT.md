# M39 报告 — 真实 Electron 应用 + LLM 真接

## 一、目标清单与结果

| 目标 | 类型 | 结果 |
|---|---|---|
| **Logseq v0.10.9** | 真实 Electron(180MB AppImage) | ✅ 完整提取+分析, 无授权(诚实) |
| **LLM 真接(降级)** | z3 符号执行推理引擎 | ✅ 求解密码 'C' + 实测验证 |
| **grantmint** | 真实 self-hosted 授权服务器 | ✅ 7 步验证链分析 + 模拟闭环 |

## 二、LLM 真接(z3 降级路径, 无 API key)

**llm_fallback_engine.py**: capstone 反汇编 → z3 符号执行 → 求解密码

```
对 M38 auth-license 实测:
  反汇编 23 条 → 定位 cmp eax 0x43 @ 0x400086 → z3 求解 password='C'
  验证: ./auth-license C → OK rc=0 ✅
```

**设计**: 无 API key 时降级到纯 Python 深度推理(z3 是 SMT 求解器,
对"cmp 立即数"类校验直接求解——比 LLM 更精确, 因为是数学求解)。

## 三、真实网络验证(grantmint)

**协议**: Ed25519 签名 token(header.payload.signature) + 7 步验证链
(结构→alg pin→typ pin→签名→版本→产品→时间)

**grantmint_sim.py 模拟闭环 6 场景实测**:
```
正常 token   -> OK
篡改 payload -> FORGED(签名不匹配)
过期 token   -> EXPIRED
未生效 token -> NOT_YET_VALID
错产品 token -> WRONG_PRODUCT
伪造签名     -> FORGED
```

**洞见**: Ed25519 签名验证**数学上不可绕过**(无私钥时)——与密码比较类
校验的本质区别。绕过只能 patch 验证调用或攻击部署弱点(时钟/配置)。

## 四、验收达成

- ✅ 至少 1 个真实 Electron 应用处理(Logseq 完整提取+分析)
- ✅ LLM 真接或有完整降级路径(z3 符号执行, 实测求解+验证)
- ✅ 至少 1 个真实网络协议分析(grantmint 7 步链 + 6 场景模拟)
- ✅ 测试全绿(见 test_m39.py)

## 五、交付

- `real-electron/LOGSEQ_REPORT.md` — Logseq 分析(真实)
- `real-electron/llm_fallback_engine.py` — z3 推理引擎
- `real-electron/grantmint_sim.py` — 网络协议模拟闭环
- `real-electron/NETWORK_PROTOCOL_REPORT.md` — grantmint 协议分析
- `real-electron/tests/test_m39.py` — 测试

## 六、边界

- Logseq/MarkText 均为开源免费(无授权可破 = 真实结论, 不伪造)
- grantmint 模拟为教学闭环, 不对真实服务发起任何请求
- 云端授权(Logseq 云同步)不在桌面工具链范围
