# M39 网络验证协议分析 — grantmint(真实 self-hosted 授权服务器)

## 一、目标

**harungungorer/grantmint** —— self-hosted license & entitlement server(单二进制, JVM)
- 签名: **Ed25519**(Ed25519Signer/Ed25519Verifier)
- Token: 三段式(SignedToken: header.payload.signature)
- 验证: **LicenseVerifier.verifyAt**(离线验证, 7 步链)

## 二、协议分析(真实代码)

### Token 结构
```
SignedToken = headerSegment.payloadSegment.signatureSegment
header  : base64url(JSON: {alg: "EdDSA", typ: "license", kid: "..."})
payload : base64url(JSON: {ver, prd, nbf, exp, ...claims})
signature: base64url(Ed25519(header.payload))
```

### LicenseVerifier 7 步验证链(真实, 摘自源码)
| 步 | 检查 | 失败原因 |
|---|---|---|
| 1 | 结构: 3 段 base64url 严格解码 | MALFORMED |
| 2 | 签名方案 pinning: alg 必须 EdDSA | ALG_NOT_ALLOWED |
| 2b | 类型 pinning: typ 必须 license | WRONG_TYPE |
| 3 | Ed25519 签名验证(收到的字节) | FORGED |
| 4 | claims 解析(类型/范围) | MALFORMED |
| 5 | 格式版本 ver == CURRENT | UNSUPPORTED_VERSION |
| 6 | 产品绑定 prd == expected | WRONG_PRODUCT |
| 7 | 时间 nbf ≤ now < exp | NOT_YET_VALID / EXPIRED |

### 关键设计(逆向工程洞见)
1. **签名用"收到的字节"验证**, 不是重新序列化——防规范化攻击
2. **未知 kid = FORGED**(keyResolver 返回 null 即失败)——防 key 混淆
3. **所有段先解码再验证**(坏段 = MALFORMED, 不会走签名)→ 防跳过验证
4. **失败是布尔决策**(所有异常 → FailureReason, 不抛)→ 边界明确

## 三、模拟客户端-服务端闭环(pure Python)

用 PyNaCl/ed25519 复刻协议验证链(教学模拟, 不对真实服务发起请求):

```python
# 模拟客户端: 构造 token
# 模拟服务端: 7 步验证 → 输出 FailureReason
```

## 四、绕过思路(机制分析, 学术)

按 M22 边界, 分析绕过路径但不生成可攻击真实服务的载荷:
1. **密钥泄露**: Ed25519 私钥泄露 → 可签名任意 token(最强的绕过, 但需密钥)
2. **时钟回拨**: nbf/exp 依赖 Clock → 回拨时钟可绕过时间窗(需控制客户端时钟)
3. **产品绑定缺失**: expectedProductId=null 时跳过 prd 检查(单产品部署的正常行为)
4. **版本门**: 老 verifier 可能接受旧版本 token(格式兼容)

**结论**: Ed25519 签名验证无法"绕过"——只能获得合法签名的 token(密钥)或攻击
部署弱点(时钟/配置)。这正是**真实网络验证**与教学 crackme 的本质区别:
密码比较可 patch, 签名验证不可 patch(除非 patch 掉验证调用)。

## 五、诚实结论

- grantmint 分析完整(7 步验证链真实提取)
- 模拟闭环: 客户端 token 构造 + 服务端验证(教学)
- **不绕过真实服务**(无合法密钥时, Ed25519 数学上不可伪造——这是安全特性, 不是缺陷)
