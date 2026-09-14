# 六段工作流逐段拆解

对应视频第 6 步的 PowerShell 链。本文件讲**每段在做什么、为什么要有这一段**，
命令模板在 SKILL.md 第四节。

---

## 段 1：目标定位

**视频原文**：`$p=C:\Users\石井\Desktop\*.lnk; $s=Get-Item -LiteralPath $p; $sw=New-Object -ComObject WScript.Shell...`

**在做什么**：从桌面快捷方式反查真实安装路径。
`.lnk` 是 Windows 的快捷方式，用 `WScript.Shell` COM 对象读它的 `TargetPath`。

**为什么需要**：用户"拖入"的往往是个快捷方式，不是真实路径。
不解析的话，后面所有段都会在错误的目录下找。

**POSIX 等价**：`readlink -f`。macOS 上拖进来的是 `.app` 目录，
真实二进制在 `Contents/MacOS/` 下。

**常见失败**：快捷方式指向已被卸载的路径（悬空链接）→ 报错并停下，不要猜。

---

## 段 2：根目录探测

**视频原文**：`$root='C:\Program Files (x86)\ByteDance\douyin'; Write-Output '==ROOT=='; Get-ChildItem -LiteralP...`

**在做什么**：确认安装根目录，列出内容。

**`==ROOT==` 这个标记值得注意**：它是给自己看的**锚点**。
模型要读命令输出，输出里混了几十行时，靠锚点定位比靠行号可靠。
这是个好习惯 —— 长输出管道里打标记，比事后数行数稳。

---

## 段 3：版本目录

**视频原文**：`$ver='...\douyin\x64\4.2.0'; Get-Item -LiteralPath (Join-Path ...`

**在做什么**：找带版本号的目录（这里是 `x64\4.2.0`）。

**为什么需要**：Electron 应用常在版本目录下放真正的 `resources/`。
在根目录找 `app.asar` 往往找不到。

**注意**：版本目录可能**不止一个**（自动更新留下的旧版本）。
要排序取最新的，并告诉用户有几个版本可选，不要默默选一个。

---

## 段 4：工具链检查

**视频原文**：`$ErrorActionPreference='SilentlyContinue'; node --version; cnpm --version; npx --yes @electr...`

**在做什么**：确认 node / npm 在，并用 `npx --yes` 拉 `@electron/asar`。

**`$ErrorActionPreference` 的切换是这一段最值得学的地方**：

| 段 | 设置 | 理由 |
|---|---|---|
| 4 | `SilentlyContinue` | 工具链**可能没装**，这是可容忍的失败，查到什么算什么 |
| 5 | `Stop` | 后面的路径**必须存在**，静默走过去会在错误路径上继续 |

很多人写 PowerShell 全程一个模式。全程 `Stop` → 第 4 段在没装 node 的机器上直接炸掉；
全程 `SilentlyContinue` → 第 5 段路径错了也照跑，最后在莫名其妙的地方失败。

**`npx --yes` 的双面性**：方便（不用先装），但每次都联网拉包，
且拉的版本不受控。生产环境应固定版本；临时用可以。

**本复现的做法**：
- `list` / `info` **不需要** `@electron/asar`（自己解析 asar 头）
- 只有 `extract` 需要，且缺失时明确提示安装方式，不静默失败

---

## 段 5：asar 定位

**视频原文**：`$ErrorActionPreference='Stop'; $src='...\x64\4.2.0\resources\a...`

**在做什么**：定位 `resources/app.asar`。

**asar 是什么**：Electron 把应用源码打包成的归档文件。
格式很简单 —— 8 字节头（含 header 大小），后面是 JSON header + 文件内容。
所以**不依赖任何库也能列出文件树**（`tools/asar_inspect.js` 就是这么做的）。

**两种打包位置**：

| 位置 | 说明 |
|---|---|
| `resources/app.asar` | 标准位置 |
| `resources/app.asar.unpacked/` | 部分文件不打包，单独放（原生模块等） |

`unpacked` 目录里的文件**不在** asar 里，列文件树时看不到 ——
`asar_inspect.js` 的 `list` 会标出 `[unpacked]`。

---

## 段 6：输出工作目录

**视频原文**：`$dst='C:\Users\石井\Documents\Codex\2026-08-02\*\work\douyin-4.2.0-asar-20260802'; Write-Ou...`

**在做什么**：建输出目录，解包产物写到这里。

**目录命名 `douyin-4.2.0-asar-20260802`**：应用名 + 版本 + 类型 + 日期。
**日期后缀防覆盖** —— 多次解包不会互相冲掉。

**路径 `Documents\Codex\<日期>\work\`**：这是 Codex 自己的工作目录约定，
不是随便挑的。好处是所有产出集中在一处，好清理。

**本复现加的一条约束**：**不原地修改原文件**。
单测里有断言 —— 解包前后原 `app.asar` 的 mtime 不变。
理由：解包是**读操作**，读操作不该有副作用。

---

## 收尾：结构查看

```bash
node tools/asar_inspect.js info    <app.asar>   # 元信息 + package.json
node tools/asar_inspect.js list    <app.asar>   # 文件树
node tools/asar_inspect.js extract <app.asar> <dst>  # 解包
```

范围写死这三件事，**不做写回、打包、打补丁**（单测有断言守着）。

---

## 逐段报告

视频状态栏显示 `Planning unpacking and decompiling steps` / `已处理 1m54s`。
即**每段都有可见进度**，不是闷头跑完再说。本复现照搬：

```
[1/6] 目标定位      → C:\...\douyin
[2/6] 根目录探测    → 12 个条目
...
```

某段失败就停下说明，**不要猜测着往下走**。
