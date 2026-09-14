# M40-B 补充报告 — 授权机制静态识别(防御视角)

## 一、范围

在 M40 保护机制识别基础上, 补充**授权相关字符串存在性统计**。
**不**定位校验函数偏移, **不**生成 patch(见判断说明)。

## 二、字符串统计(存在性, 非偏移)

### rar(WinRAR 7.23, 798KB)
| 类别 | 命中 |
|---|---|
| license_key / serial | 0 |
| registration | 0 |
| trial / expired | 0 |
| invalid | 1 |
| crypto(rsa/signature/key) | 0 |
| key_file | 0 |

**观察**: WinRAR 授权字符串几乎为零——可能的解释:
1. 字符串已剥离/混淆(商业软件常规做法)
2. 授权逻辑在共享库或独立模块
3. 用非字符串方式(如注册表键、时间戳)校验

### sublime_text(Sublime Text 4, 9.9MB)
| 类别 | 命中 |
|---|---|
| license_key / serial | 11 |
| registration | 22 |
| trial / expired | 2 |
| invalid | 155 |
| crypto(rsa/signature/key) | 24 |
| key_file | 3 |

**观察**: Sublime 有完整的授权子系统(字符串丰富)——license_key 概念 +
RSA/签名(24 处 crypto 字符串)+ 注册状态(22 处)。这是**签名验证型授权**
(与 M39 grantmint 同类机制, 无私钥数学上不可伪造)。

## 三、机制类型判断(第一性原理)

- **WinRAR**: 授权字符串剥离 → 校验可能基于注册表键/时间戳/自校验,
  需动态分析才能定位(但那是商业破解范畴, 不做)
- **Sublime**: 签名验证型授权(RSA/Ed25519 类)——**与 grantmint 同型**,
  M39 已证明"签名验证无法数学绕过, 只能 patch 验证调用或密钥泄露"

## 四、结论(边界判断)

WinRAR/Sublime 是付费商业产品(EULA 禁止逆向), 产出 patch = 制作商业
破解工具。本项目边界(M22)保持不变: 识别保护机制 ✅ / 生成绕过载荷 ❌。
教学机制演示已在 M38(M38 开源授权教学)与 M39(grantmint 协议)完成。

## 五、防御视角价值

这些统计对**防御方**有价值:
- 字符串剥离程度 → 反分析强度评估
- 授权类型(签名 vs 密钥文件) → 被攻击面分析
- crypto 字符串密度 → 签名验证是否为核心
