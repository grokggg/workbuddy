# M-B12 追溯 — M-B08 压测 v2 有效性核实

## 结论

| 项 | 结果 |
|---|---|
| M-B08 时 v2 路径 | **内层**(v2-codex-skill-injection/v2-codex-skill-injection, git show 6b93277 确认) |
| 内层版 v2 压测 | **命令通过 rc=0, 但段 10-12 走占位** |
| M-B08 220/220 对 v2 有效性 | **形式通过**(压测命令 show skill 只显示文本, 不跑破解链) |
| 记忆匣是否需补注 | **是** |

## 证据链

### 1. M-B08 时 integration v2 路径 = 内层
```
git show 6b93277:integration/cli.py
    "v2": {"dir": "v2-codex-skill-injection/v2-codex-skill-injection", ...}
```

### 2. M-B08 内层 runner_full.py = 旧版(11 处占位标记)
```
grep -c "placeholder|{PATCH}" mb08-v2/.../lib/runner_full.py → 11
```

### 3. 用 M-B08 内层版跑 run-full(教学 asar)
```
[10/12] 修改占位 [占位] → OK  {PATCH} 占位: 无校验文件命中
[11/12] 重新打包 [占位] → OK  {COMMAND} 占位: 打包解包目录 -> ...
[12/12] 输出验证 [占位] → OK  {VERIFY_CMD} 占位: 运行重新打包后的应用...
通过 10/12(段 10-12 全占位, 非真执行)
```

### 4. M-B08 压测命令对 v2 = show skill(只显示, 不跑链)
```
integration/cli.py run_stress 的 e2e["v2"] = ["show", "skill"]
→ 输出 SKILL.md 文本, rc=0 = 显示成功, 与破解链无关
```

## 更正

- M-B08 汇总"220/220 100%"对 v2 的**命令执行**有效(show skill rc=0)
- 但对 v2 的**完整处理链**(run-full 段 10-12)**形式通过**——当时走占位分支
- v2 破解链真正首次通过: **M-B10**(段 10-12 真实 sed/asar_pack/node 执行, 11/12)
- integration 真正指向修复版外层: **M-B12**
