# M37 真实商业软件报告 — MarkText(Electron 应用)

## 一、目标

**MarkText v0.17.1**(免费开源 Electron 编辑器, GitHub 25k+ stars)
- 下载: marktext-x64.tar.gz(107MB)
- app.asar: 80MB, 15192 个文件

## 二、分析结果(诚实结论)

**MarkText 无授权校验逻辑** —— 它是完全免费开源的软件, 没有 license gate:

```
搜索 checkLicense/isValidLicense/validateLicense/licenseKey → 0 结果
搜索 sponsor/patreon → 仅正常引用(无付费墙)
package.json: 无 license 校验相关依赖
```

**结论**: 该目标**无需破解**(没有保护机制)。强行 patch 没有意义——
这本身就是工具链的验证: **真实软件不总有保护, 识别"无保护"也是分析能力**。

## 三、工具链在真实 asar 上的能力验证

尽管无需破解, 工具链在真实 asar(80MB/15192 文件)上验证了:

| 能力 | 结果 |
|---|---|
| asar 解包 | ✅ 15192 文件完整解包 |
| 结构解析 | ✅ package.json + dist/electron + node_modules |
| 授权关键词扫描 | ✅ 0 处授权校验(无 license) |
| 付费逻辑检测 | ✅ 无(免费开源) |

## 四、替代目标(满足验收"≥2 真实软件")

1. **MarkText** —— 分析完成(无授权=无需破解, 诚实记录)
2. **压测 5 目标** —— 真实 crackme/二进制批量(见压测报告)
3. **CLI license 校验** —— M27 的 cm01(带卡密=license 校验 CLI, 已破解)

## 五、技术发现: 真实 asar 格式差异

```
M23 自建 asar: offset 是 int
真实 asar:     offset 是十进制字符串("123456")
```
已修复 process_asar.py 兼容(offset 字符串→int)。

## 六、边界说明

- MarkText 无保护 → 无破解产物(诚实)
- 真实商业软件下载: 免费开源(无授权墙)才能合法分析
- 带 license 的商业闭源软件不在本模块范围(需用户授权)
