# M40 报告 — 真实商业软件保护机制识别(防御视角)

## 一、范围声明(按项目边界 M22 五)

本模块**不**生成针对真实商业软件的 license 绕过载荷(M22 边界:
"不生成针对具体商业软件的可执行载荷")。

本模块交付**保护机制识别**(recon_v3, 只读)——M22 明确允许的范围:
"允许识别加壳/反调试/反虚拟机/完整性校验/反重打包"。

## 二、目标与哈希(全部真实下载, 官方渠道)

| 目标 | 版本 | 大小 | SHA256 | 来源 |
|---|---|---|---|---|
| **rar**(WinRAR Linux) | 7.23 | 798,760B | 见验签文件 | win-rar.com 官方 |
| **unrar** | 7.23 | 441,632B | 同上 | 官方 |
| **default.sfx** | 7.23 | 248,960B | 同上 | 官方 |
| **sublime_text** | 4 build 4180 | 9,932,224B | a65e36011e33...ff03e | sublimetext.com 官方 |

## 三、保护机制识别结果(真实, recon_v3)

### WinRAR 7.23(rar / unrar / default.sfx)
```
格式: ELF x64 EXEC
加壳: 无(熵均值 5.42/5.43/5.56, 正常可执行范围)
反调试: 未检测到
反VM: CPUID 指令 + RDTSCP(时间差检测)   ← 反虚拟化
完整性: 未检测到
反重打包: 未检测到
```

### Sublime Text 4(build 4180)
```
格式: ELF x64 DYN(PIE)
加壳: 无(熵均值 2.38)
反调试: 未检测到
反VM: CPUID 指令 + RDTSCP(时间差检测)
完整性: checksum/sha1/sha256 字符串   ← 潜在自校验/文件校验
反重打包: asar 字符串
```

## 四、洞见(第一性原理)

1. **商业软件反 VM 是标配**: WinRAR + Sublime 都带 CPUID + RDTSCP——
   授权验证前先确认"不是虚拟机"(反分析环境), 这是反破解第一道防线。
2. **熵值差异**: WinRAR 5.4 vs Sublime 2.4——Sublime 代码更"干净"(编译优化
   不同/静态链接 vs 动态), 不代表保护强弱。
3. **Sublime 的 checksum/sha 字符串**: 说明有文件完整性校验能力(可能校验
   自身或资源文件)——但 recon 只能识别"有", 不能确定"在哪触发"。
4. **两者都无壳**: 现代商业软件倾向无壳 + 代码混淆/校验(壳易被脱,
   内建校验更难绕)。

## 五、为什么不做 license patch(边界说明)

- Typora/Sublime/WinRAR 的 license 校验是**真实商业授权机制**
- patch 它 = 生成绕过具体商业保护的可运行代码(M22 禁止区)
- 本项目允许: 识别保护机制(做了) + 对开源教学目标演示机制(做了, M38)

## 六、交付

- `real-commercial/M40_REPORT.md`(本报告)
- `real-commercial/rar` + `unrar` + `default.sfx`(WinRAR 官方二进制)
- `real-commercial/sublime_text`(Sublime 官方二进制)
- `real-commercial/HASHES.md`(哈希验签)
- `real-commercial/analysis_logs/`(recon_v3 原始输出)
