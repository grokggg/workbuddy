# v5-jump-patch — AI 辅助改跳转

> 复现 B 站视频 [BV1py8668Eqv](https://www.bilibili.com/video/BV1py8668Eqv)(逐日逆向, 934s, AI 辅助改跳转)。
> **流程完整实现: 分析 -> 定位 -> 修改 -> 验证, 全部真实执行。**
> **只改副本, 不碰原件**(与仓库 copy_patch.py 一致)。

## 一、30 秒跑通

```bash
./install.sh                        # 环境自检 + 跑全部测试

# 完整流程(分析->定位->修改->验证)
python3 cli.py jump-patch <目标文件> --work-dir <工作目录>

# 只分析
python3 cli.py analyze <目标文件>

# 带验证命令(真实运行副本)
python3 cli.py jump-patch <目标文件> --verify-cmd "python3 -c print('ok')"
```

## 二、流程(转录 381s-831s)

| 步 | 名称 | 转录依据 | 实现 |
|---|---|---|---|
| 1 | 分析文件 | "让他分析下这个软件的流程...读取文件...PE 结构" (381s-473s) | 真实读文件 + PE 检测 + 字符串提取 |
| 2 | 定位跳转 | "条件跳转" (583s) | 扫描 x86 条件跳转(JE/JNE/JZ 等) |
| 3 | 修改 | "把这六个字节改为 6 个 NOP" (594s) | 复制副本 + 跳转字节 → NOP |
| 4 | 验证 | "密码正确看到没有他已经给我们处理好了" (831s) | 字节验证 + 真实运行副本 |

## 三、支持的指令

**短跳转**(0x70-0x7F): JE/JZ, JNE/JNZ, JO, JNO, JB, JAE, JBE, JA, JS, JNS, JL, JGE, JLE, JG
**近跳转**(0F 80-8F): 同上 near 变体

## 四、实测输出(真实日志)

```
[1/4] analyze  → OK  /tmp/demo-exe.bin: 301 字节, PE 文件 (x86)
      字符串样本: ['password_check', 'login', 'admin']
      条件跳转: 7 处  首个: offset=0x100 JE/JZ (short)
[2/4] locate   → OK  定位: offset=0x100 JE/JZ (short) (opcode 74, 2 字节)
[3/4] modify   → OK  副本: /tmp/v5-work/demo-exe.bin.patched
      偏移 0x100: 7405 -> 9090 (NOP)
[4/4] verify   → OK  副本偏移 0x100: 已 NOP(2 字节) ✓
通过 4/4
```

**边界验证**: 原件 @0x100 = `74 05`(JE), **未动**。

## 五、目录结构

```
v5-jump-patch/
├── cli.py               # CLI(jump-patch / analyze)
├── lib/engine.py        # Analyzer + Patcher + Verifier + 总引擎
├── tests/test_engine.py # 17 例单测
└── README.md
```

## 六、测试

```bash
./install.sh            # 17 例全绿
python3 tests/test_engine.py -v
```

| 组 | 例数 | 覆盖 |
|---|---|---|
| Analyzer | 5 | 分析/PE/字符串/跳转扫描 |
| Patcher | 4 | 副本/NOP/字节验证/原件不动 |
| Verifier | 3 | 运行/缺失/补丁验证 |
| 总引擎 | 5 | 全流程/带运行/边界 |
| **合计** | **17** | 全绿 |

## 七、边界

- 流程完整实现 ✅
- 具体目标参数由用户填(`<目标文件>`)✅
- 测试在本地 mock 环境 ✅
- **只改副本, 不碰原件** ✅
- 修改只做 NOP 跳转(结构操作), 不注入恶意逻辑 ✅

## 八、依赖

- Python 3.8+ (纯标准库, 零第三方)
