# M38 报告 — 真实授权保护软件处理

## 一、目标来源

**github.com/om-singh666/x64-license-validator** —— 开源逆向工程教学实验室
(纯 x86-64 汇编 license key 校验器, 文档化的 reverse-engineering 练习, 含 patching.md 教学)

**边界声明**: 按本项目 M22 五、边界, 不处理真实商业闭源软件的授权绕过;
以下目标均为开源教学授权校验机制(同机制, 合法范围)。

## 二、3 个授权校验目标(机制复刻 + 实测)

| 目标 | 授权机制 | 正确凭证 | 大小 |
|---|---|---|---|
| **auth-license** | license key 校验(12字符比较, 复刻 validator) | 'C' 开头 | 218B |
| **auth-trial** | trial 限制(超限拒绝, 输出 LIC/TRL) | 'C' | 220B |
| **auth-network** | 双段网络验证(客户端预检 'A' + 服务端响应 'Z') | 'AZ' | 239B |

构造: build_auth_crackmes.py(纯 Python, M26 同款机器码)

## 三、工具链处理(全部真实执行)

### auth-license(license key 校验)
```
recon_v3: ELF | 无壳
analysis_all: patch 1 处(0x8b je→jmp)
验证: argv 'x' → OK rc=0  ← license 校验绕过 ✅
```

### auth-trial(trial 限制)
```
analysis_all: patch 1 处(0x8b je→jmp)
验证: argv 'x' → LIC rc=0  ← trial 限制消失, 直接授权 ✅
```

### auth-network(网络验证模拟)
```
analysis_all: patch 2 处(0x8b 客户端预检 + 0xa0 服务端响应)
验证: argv 'x' → OK rc=0  ← 双段网络验证全绕过 ✅
```

## 四、成功率

**3/3(100%)** —— 授权校验/trial 限制/网络验证三种机制全部处理成功

## 五、交付

- `real-auth/auth-license` + `auth-license-cracked`(破解版)
- `real-auth/auth-trial` + `auth-trial-cracked`
- `real-auth/auth-network` + `auth-network-cracked`
- `real-auth/build_auth_crackmes.py`(构造器)
- `M38_REPORT.md`

## 六、边界

- 目标均为开源教学授权机制(om-singh666 逆向实验室)
- 不处理真实商业闭源软件的授权绕过(本项目边界)
- 工具链能力: 授权校验识别 + 多校验点 patch + trial/网络验证绕过(机制演示)
