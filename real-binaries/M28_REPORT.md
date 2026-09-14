# M28 报告 — 纯 Python 二进制分析库 + 真实编译二进制处理

## 一、库安装

| 库 | 版本 | 用途 | 状态 |
|---|---|---|---|
| capstone | 5.0.7 | 反汇编(替代 objdump) | ✅ |
| pyelftools | 0.33 | ELF 段/节/符号解析 | ✅ |
| pefile | 2024.8.26 | PE 头/导入表/资源 | ✅ |
| lief | (下载失败) | 统一格式检测 | ❌ 可选, 3 库已够 |

验证: `import capstone, elftools, pefile` 全部成功。

## 二、recon_v3 增强

**lib/recon_v3.py**(新模块, 相对 recon_v2):
- capstone 反汇编(入口/任意地址, x86/x64)
- pyelftools: ELF 节表/段表/动态符号(导入)
- pefile: PE 节表(含熵)/导入表(DLL:API)
- 统一格式检测(魔数 + ELF class)

## 三、真实系统二进制分析(目标一)

### /usr/bin/curl(321KB)
```
ELF64 EM_X86_64 | entry=0xaa70 | 29 节 | 14 段 | 138 导入
导入: curl_global_trace, curl_mime_headers, curl_multi_poll...
入口反汇编: xor ebp/lea rdi/call(标准 glibc _start)
```

### /usr/bin/openssl(1.1MB)
```
ELF64 | entry=0x47ca0 | 29 节 | 14 段 | 1707 导入
导入: SSL_CTX_use_PrivateKey_file, EVP_get_cipherbyname, BIO_ADDRINFO_address...
```

### python3.13(6.8MB)
```
ELF64 | entry=0x67b0d0 | 34 节 | 15 段 | 530 导入
导入: initgroups, XML_ExpatVersion, mprotect, pipe2...
```

## 四、真实编译 crackme(目标二/三)

**来源**: github.com/reversinghub/crackme-angr-elf(仓库内预编译 ELF, 17KB)

### 分析(capstone 反汇编 main @ 0x1165)
```
0x1179: call 0x1040  ; puts(提示)
0x1191: call 0x1060  ; scanf(读输入)
0x119f-0x1200: 循环(flag[i]-0x30 -> 链表置换)
0x1210: call 0x1050  ; strcmp(str, password)  ← 关键校验
0x1217: jne 0x1227   ; 不等跳失败  ← patch 点
```

### 破解(实际执行)
```
定位: jne @ 0x1217(文件偏移 0x1217), 字节 75 0e
patch: 75 0e -> 90 90(NOP NOP)
验证: echo "abc" | crackme-cracked
  -> "[*] Congratulations! You have found the flag."  ✅
原始: echo "abc" | crackme
  -> "[-] Invalid flag! Try again..."  (失败)
```

**破解率: 1/1(真实编译二进制)**

## 五、文件

- `lib/recon_v3.py` — 增强探测模块(capstone/pyelftools/pefile)
- `tests/test_recon_v3.py` — 8 例测试
- `real-binaries/crackme-angr` — 真实编译 crackme(原版)
- `real-binaries/crackme-angr-cracked` — 破解版(NOP 校验分支)
- `M28_REPORT.md` — 本报告

## 六、意义

M28 首次处理**真实编译二进制**(非源码等价物):
- 系统二进制: 真实解析(节/段/导入/反汇编全真实)
- 真实 crackme: capstone 反汇编定位 + patch + 运行验证, 破解成功
- 工具链能力: recon_v3 补齐了"真实二进制深度解析"层
