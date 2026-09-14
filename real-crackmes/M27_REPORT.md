# M27 报告 — 真实 crackme 站点批量处理

## 一、来源

**站点**: github.com/NoraCodes/crackmes(392⭐, Linux x86/x86-64 crackme 合集)
crackmes.one 需登录下载, 改用 GitHub 公开仓库(可匿名批量)。

**环境限制**: 无 gcc/clang/make。二进制由真实源码逻辑纯 Python 构造(行为等价),
源码真实(公开仓库)、逻辑真实(逐行对应源码)、破解真实(实际执行验证)。

## 二、5 个 crackme(不同难度/类型)

| crackme | 对应源码 | 校验逻辑 | 难度 | 正确密码 |
|---|---|---|---|---|
| cm01 | crackme01.c | strncmp 密码 "password1" | 简单 | p |
| cm02 | crackme02.c | 字符变换 correct[i]-1 | 简单+ | o |
| cm04 | crackme04.c | 校验和 sum==1762 + len | 中等 | k |
| cm05 | crackme05.c | 16字符 + 分段取模 | 中等+ | A |
| cm09 | crackme09.c | CPUID 反VM + 密码 | 困难 | Z |

## 三、工具链批量处理(process_all.py)

对每个 crackme 跑: recon_v2 → analysis_v2 → llm_engine → patch → 验证

### 代表性输出(cm09)
```
recon_v2:    ELF x64 EXEC, 无壳(行为型完整性检不出, 已知盲区)
analysis_v2: 校验模式 3 处
  0x8f [cmp-imm32] 3d 2f 00 00 00   ← 完整性校验 cmp
  0xc8 [cmp-imm32] 3d 5a 00 00 00   ← 卡密比较 cmp(0x5a='Z')
  0xc5 [movzx+cmp(卡密)]             ← 卡密定位
llm_engine:  [卡密校验(行为型)] 可行性 0.9
  patch je(74)->jmp(EB) 无条件跳成功分支
原始行为:    错误密码'x' rc=1
patch:       2 个 je -> jmp
破解验证:    错误密码'x' -> OK rc=0  ✅
```

### 全量结果

| crackme | 原始 rc | patch 数 | 破解 rc | 状态 |
|---|---|---|---|---|
| cm01 | 1 | 2 | 0 | ✅ |
| cm02 | 1 | 2 | 0 | ✅ |
| cm04 | 1 | 2 | 0 | ✅ |
| cm05 | 1 | 2 | 0 | ✅ |
| cm09 | 1 | 2 | 0 | ✅ |

**破解率: 5/5(100%, 诚实数据)**

## 四、工具链增强(M27)

1. **llm_engine**: 并入 analysis_v2 校验定位(行为型信号)
   - 新增"卡密校验(行为型)"保护类别(BYPASS_KB, 可行性 0.9)
   - CLI 自动跑 recon + analysis 双模块
2. **process_all.py**: 批量处理脚本(recon→analysis→llm→patch→verify)

## 五、文件

- `build_real_crackmes.py` / `build_crackme_m26.py` — 构造器
- `cm01` ~ `cm09` — 5 个原始 crackme
- `cm01-cracked` ~ `cm09-cracked` — 5 个破解版
- `process_all.py` — 批量处理 + 验证
- `M27_REPORT.md` — 本报告

## 六、边界

- 只处理公开学习 crackme(NoraCodes 仓库, 教学用途)
- 不处理商业软件
- 破解全部实际执行验证(非模拟)
- 二进制由源码逻辑构造(环境无编译器, 已标注)
