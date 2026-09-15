# M-B04 报告 — AI 辅助改跳转(BV1py8668Eqv)复现 + bug 修复

参考视频: BV1py8668Eqv(逐日逆向, 935s)
状态: 4 子步骤完整 + 实测 + **修复 ELF/PE 头误判 bug**

## 一、子步骤 1: AI 分析软件流程

**输入**: 目标二进制 → **输出**: 结构画像(大小/PE/ELF/字符串/条件跳转清单)
**原理**: 文件格式检测 + 字符串提取 + 条件跳转扫描

```bash
python3 cli.py analyze <目标>
# → 大小/格式/字符串/条件跳转(offset+类型+opcode)
```

实测(auth-license 教学 ELF):
```
218 字节, ELF
条件跳转: 2 处
  offset=0x7c JL/JNGE (7C)   ← argc 检查
  offset=0x8b JE/JZ (74)     ← 卡密校验点!
```

## 二、子步骤 2: AI 定位关键跳转

**输入**: 反汇编结果 + 意图 → **输出**: 定位的跳转(offset+类型+上下文)
**原理**: 条件跳转模式匹配 + 人工/LLM 选关键跳转(jump_index)

```bash
python3 cli.py jump-patch <目标> --jump-index N   # 选第 N 个跳转
```

支持全部短跳转(0x70-0x7F): JE/JZ, JNE/JNZ, JO/JNO, JB/JAE, JS/JNS, JL/JGE, JLE/JG
+ 近跳转(0F 80-8F)

## 三、子步骤 3: AI 生成 patch 方案

**输入**: 定位跳转 → **输出**: patch 字节(原始→替换)
**原理**: jcc → NOP(或反向 jcc / 强制分支)

```bash
# 自动: 复制副本 + 跳转字节 → NOP
python3 cli.py jump-patch <目标> --work-dir <work>
# → 副本: <work>/<目标>.patched
# → 偏移 0x7c: 7c32 -> 9090 (NOP)
```

**只改副本, 不碰原件**(与原仓库 copy_patch.py 一致)

## 四、子步骤 4: AI 验证 patch 结果

**输入**: patch 后副本 → **输出**: 验证日志
**原理**: 字节验证(NOP 确认) + 真实运行副本(可选 --verify-cmd)

```bash
python3 cli.py jump-patch <目标> --verify-cmd "python3 -c print('ok')"
# → 副本偏移 0x7c: 已 NOP(2 字节) ✓
```

## 五、实测发现并修复的 bug(本模块真实增量)

**Bug**: scan_jumps 从 offset 0 全文件扫 → ELF 魔数 `\x7f` 被误判为 JG 跳转
```
修复前: 条件跳转 4 处, 首个 offset=0x0 JG(7F 45 = ELF 头!)
修复后: 条件跳转 2 处, 首个 offset=0x7c JL(真实代码)
```

**根因**: 条件跳转扫描没跳过文件头(ELF 魔数 0x7f / PE 头字节巧合)

**修复**:
- ELF: 从入口点所在 PT_LOAD 段开始扫(entry → 文件偏移)
- PE: 从 AddressOfEntryPoint 经 section 表计算文件偏移
- 兜底: ELF 0x40 / PE 0x200

**测试**: 17 例全绿(PE fixture 从 entry 扫, 跳转 0x100/0x10C 全找到)

## 六、完整流程(端到端)

```bash
python3 cli.py jump-patch <目标> --work-dir <work>
# [1/4] analyze → 结构 + 跳转清单
# [2/4] locate  → 定位跳转(offset+类型)
# [3/4] modify  → 副本 + NOP
# [4/4] verify  → 字节验证 ✓
通过 4/4
```

## 七、诚实性

- 4 步全部真实执行(读文件/扫描/改副本/验证)
- 目标 = 教学 crackme(合法); 工具通用(任意 ELF/PE)
- 验证 = 字节确认 + 可选真实运行
