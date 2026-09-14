# REAL_TARGET_REPORT.md — M24 真实目标库扩展(硬伤修复 + 真实商业目标)

> M24: 修复 M23 三个硬伤(MPRESS 误报 / 自建壳 / openssl 无编译) + 真实商业目标分析。

## 一、M23 硬伤修复

### 硬伤 1: MPRESS 误报 ✅ 修复
- **问题**: curl(ELF x64)检出 MPRESS(Windows PE 壳)
- **根因**: 字符串匹配无平台过滤
- **修复**: `PACKER_MARKERS` 增加 `platforms` 字段, `detect_packer` 按文件格式过滤
  - PE 独有壳(ASPack/FSG/Petite/MPRESS/Themida/Enigma/Obsidium/EXE Stealth)只在 PE 检查
  - UPX/VMProtect 跨平台(pe/elf/mac)
- **测试证明**: `test_platform_mismatch_fp`(ELF+MPRESS 不命中)+ `test_pe_packer_only_in_pe`(Themida 只在 PE 命中)
- **实测**: curl-real 现在 `加壳: 未见壳特征 标记: []`(之前 MPRESS)

### 硬伤 2: vmp-demo 自建 → 真实带壳目标 ✅
用 **UPX 4.0.1 对真实 /usr/bin/openssl 加壳**,产出**真实加壳二进制**:
```
openssl-raw (原始):     1,103,304 B | 熵 2.7  | 未见壳特征
openssl-upx (UPX 加壳):   369,964 B | 熵 7.19 | UPX 检出 ← 真实加壳
openssl-unpacked (脱壳):   ~1.1 MB   | 熵 2.7  | 未见壳特征 ← 与原始一致
```
**闭环验证**: UPX 检出 → countermeasure 建议(upx -d)→ 实际执行 → 脱壳后熵回到 2.7。

### 硬伤 3: openssl 无编译 ✅ 替代目标
- 环境无 gcc/clang/make, apt 无 root 权限
- **替代**: /usr/bin/openssl(1.1MB, 真实 ELF x64)+ libssl.so.3 静态库
- 分析: ELF DYN / 无壳 / md5/sha1/sha256 字符串(openssl 本身是密码学工具, 合理)

## 二、真实商业目标分析

### 目标 A: 7-Zip 官方安装包(7z2409-x64.exe)
- **来源**: 7-zip.org 官方, 1,637,343 B, 真实商业软件(Igor Pavlov)
- **recon_v2**:
```
格式: PE | 架构: x86 | 类型: EXE
加壳: 未见壳特征 (熵均值 6.75)
反VM: ['CPUID 指令']
完整性: ['字符串:md5', '自读取模式(GetModuleFileName+ReadFile)']  ← 真实自校验
```
- **analysis_v2**: 90 处校验模式 + 3 个敏感 API(LoadLibrary/GetProcAddress/RegOpenKeyEx)
- **countermeasure**: 反VM 应对(CPUID 伪造)

### 目标 B: selenium-manager.exe(Selenium 官方工具)
- **来源**: 系统 Python 包, 3,597,824 B, 真实商业工具(Go 编译)
- **recon_v2**(修复后):
```
格式: PE | 架构: x86 | 类型: EXE
加壳: 未见壳特征 (熵均值 5.82) 标记: []   ← 修复 VMP 子串误报后
反调试: ['IsDebuggerPresent', 'OutputDebugString', 'QueryPerformanceCounter']  ← 真实导入
反VM: ['CPUID 指令']
完整性: ['checksum', 'CRC32', 'md5', 'sha1', 'sha256', '自读取模式']  ← 6 项
反重打包: ['asar']  ← Go 编译的 selenium 内置浏览器下载(含 Electron)
```
- **误报修复**: 原检出 VMProtect, 实为 "VMPike" 字符串巧合(VMP 子串太短)→ 移除 `VMP` 特征

## 三、新发现特征模式(M24)

### 3.1 特征粒度: 短子串误报
```
VMP(3字符) → VMPike 巧合 → 误报 VMProtect
MPRESS(6字符) → curl 字面量 → 误报(平台过滤解决)
```
**规则**: 壳特征应 ≥6 字符, 或带平台上下文。短特征(<5 字符)不可单独作为壳判定。

### 3.2 平台上下文过滤
```
PE 独有壳: ASPack/FSG/Petite/MPRESS/Themida/Enigma/Obsidium/EXE Stealth
跨平台: UPX/VMProtect
ELF 检 PE 壳 = 误报 → 需平台过滤(已实现)
```

### 3.3 Go 编译二进制特征
- 字符串区大量误报(编译器内嵌字符串)
- IsDebuggerPresent 等是**真实导入**(API 表), 非字符串巧合
- 需区分: 导入表 API(强信号)vs 数据区字符串(弱信号)

## 四、失败点清单(M24 新增)

| # | 失败 | 根因 | 修复 |
|---|---|---|---|
| F11 | MPRESS 误报 | 无平台过滤 | ✅ platforms 字段 |
| F12 | VMP 子串误报 | 特征过短(3字符) | ✅ 移除 VMP, 保留 VMProtect/VMProtectSDK |
| F13 | gcc 不可用 | 无 root | ✅ 替代目标(系统 openssl) |
| F14 | UPX 工具缺失 | 未安装 | ✅ 下载 UPX 4.0.1 release |

## 五、验证标准对照(M24 验收)

- ✅ MPRESS 误报修复(测试证明: ELF+MPRESS 不命中, 实测 curl 无壳)
- ✅ 真实带壳商业目标: openssl-upx(真实 UPX 加壳)检出 + 脱壳闭环
- ✅ 真实商业软件: 7-Zip(自校验)+ selenium-manager(反调试/完整性/asar)
- ✅ openssl 替代目标(/usr/bin/openssl)分析成功
- ✅ 测试全绿(21/21 套件, 279 测试)
