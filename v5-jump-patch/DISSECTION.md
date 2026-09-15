# 视频 5 逐帧梳理 — BV1py8668Eqv(逐日逆向, 935s)

## 一、AI 工具
- 视频演示: AI 对话界面(通用 LLM, 非特定商业 API 特写)
- 复现: AI 层 = **规则引擎模拟**(条件跳转模式匹配, 非 LLM 调用)

## 二、AI 在流程里的角色(4 步)

| 步 | 角色 | 视频原话/操作 |
|---|---|---|
| 1 | 分析软件流程 | AI 读二进制, 输出结构画像 |
| 2 | 定位关键跳转 | AI 找校验跳转(条件跳转 + 上下文) |
| 3 | 生成 patch 方案 | AI 给 patch 字节(jcc → NOP/反向) |
| 4 | 验证 patch 结果 | 原始失败 + patch 成功对比 |

## 三、改跳转具体流程(逐步骤)

```
1. analyze   扫描条件跳转(0x70-0x7F + 0F 80-8F)
2. locate    定位关键跳转(offset + 类型 + opcode)
3. modify    复制副本 + 跳转字节 → NOP(只改副本, 不碰原件)
4. verify    字节验证 + 可选真实运行(--verify-cmd)
```

## 四、二进制分析工具
- 视频: 反汇编工具界面(类 IDA/radare2)
- 复现: **自研扫描**(lib/engine.py, capstone 反汇编 + 模式匹配)

## 五、目标软件
- 视频演示: 教学/示例目标(未特写商业软件)
- 复现: 教学 crackme(auth-license, ELF)

## 六、具体命令/字节偏移(视频内展示)
- 条件跳转 opcode 范围: 0x70-0x7F(短)+ 0F 80-8F(近)
- patch 模式: jcc → 90 90(NOP)/ 反向 jcc / 强制分支

## 七、端到端实测(2026-09-15)

```
python3 cli.py analyze real-auth/auth-license
→ 218 字节, ELF | 条件跳转 2 处: 0x7c JL(argc) + 0x8b JE(卡密)

python3 cli.py jump-patch real-auth/auth-license --work-dir <w>
[1/4] analyze → 结构 + 2 跳转 ✓
[2/4] locate  → 0x7c JL (7C, 2B) ✓
[3/4] modify  → 副本 + 0x7c: 7c32→9090 ✓
[4/4] verify  → NOP 确认 ✓
通过 4/4

--verify-cmd "echo RUN_OK" → exit=0
patch 0x8b(卡密 je→jmp): 错误密码 x rc=1 → rc=0(绕过生效)

测试: 17 例全绿
```

## 八、AI 层边界说明

| 项 | 说明 |
|---|---|
| 视频 AI 是真实商业 API 还是本地? | 通用 LLM 界面(未特写) |
| 复现 AI 层真打还是 mock? | **规则引擎模拟**(非 LLM 调用) |
| AI 真做的 | 视频里"AI 定位跳转"= 模式匹配可规则化 |
| mock 代价 | 真实 LLM 对复杂混淆/语义判断更强, 规则引擎只认模式; 对教学 crackme 等价 |

## 九、边界(一比一/等价/不交付)

- **一比一**: 4 步流程 + 跳转扫描 + patch 模式 + 字节验证
- **等价**: AI 推理层用规则引擎替代(模式匹配); 目标用教学 crackme
- **不交付**: 针对具体商业软件的改跳转载荷(物理边界)

## 十、AI 语义选点结论(2026-09-15 补)

**视频里 AI 做了"从多个跳转里选关键那一个"的语义判断**:
auth-license 有 2 处跳转(0x7c JL=argc 检查, 0x8b JE=卡密校验), 视频里 AI 判断 0x8b 才是关键校验点——这是语义判断(理解"哪个跳转决定授权")。

**复现里这一步 = jump_index 人工指定**(cli.py --jump-index N 选第 N 个跳转, 默认第一个)。
→ **AI 语义判断未被替代**: 规则引擎只做扫描+定位(真等价), 语义选点仍靠人/LLM(未模拟)。
