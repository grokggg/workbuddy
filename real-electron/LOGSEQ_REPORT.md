# M39 Logseq 分析报告 — 真实 Electron 应用

## 一、目标

**Logseq v0.10.9**(privacy-first, open-source knowledge platform, GitHub 30k+ stars)
- 下载: logseq-linux-x64-0.10.9.AppImage(180MB)
- 提取: --appimage-extract(真实 AppImage 解包)
- 结构: resources/app(未打包 asar, 直接展开)

## 二、提取过程(真实)

```
./logseq.AppImage --appimage-extract
→ squashfs-root/
  ├── Logseq(主二进制)
  ├── chrome_100_percent.pak / v8_context_snapshot.bin(Chromium 运行时)
  ├── resources/app/(应用代码, 未打包 asar)
  │   ├── electron.js / forge.config.js(主进程)
  │   ├── js/(前端 bundle)
  │   └── node_modules/(依赖)
```

**发现**: Logseq 0.10.9 **未打包 asar**——resources/app 直接展开。
(electron-forge 配置, 无 app.asar)

## 三、授权校验扫描(诚实结论)

```
grep license/activation/isPro/premium/purchase/plan(排除 node_modules + 前端库)
→ 0 处业务授权校验

命中均为前端依赖库的 license 注释:
  interact.js / react.js / tabler.ext.js / excalidraw.js(第三方库版权头)

package.json: "A privacy-first, open-source platform" — 开源免费
```

**结论: Logseq 0.10.9 无授权限制**(完全免费开源)。
与 M37 MarkText 相同——**无保护软件无需破解**, 工具链识别"无授权"也是能力。

## 四、为什么(第一性原理)

Logseq 的商业模式 = 开源免费 + 云同步服务(收费)。桌面端无 license gate,
授权在**云端服务层**(账号/订阅)——这不是桌面二进制能 patch 的。

**诚实边界**: 处理云端授权 = 攻击他人服务, 不在工具链范围。
桌面端"无授权可破"就是真实结论。

## 五、与 M37 MarkText 对比

| 项 | MarkText | Logseq |
|---|---|---|
| 版本 | v0.17.1 | v0.10.9 |
| 打包 | app.asar(80MB) | 未打包(直接展开) |
| asar 处理 | 需解包 | 无需 |
| 授权限制 | 无 | 无 |
| 商业模式 | 免费开源 | 免费开源+云服务 |
| 结论 | 无需破解 | 无需破解 |
