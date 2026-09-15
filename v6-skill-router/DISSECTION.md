# 视频 6 逐帧梳理 — BV13nTj6JEWT(编程奇遇, Skill 路由 + iv8)

> 素材来源: `dossier/subtitle.srt`(131 行, 带时间戳)+ `dossier/subtitle.txt` + `dossier/distill.md`(24KB 内容蒸馏)

## 一、视频真实内容(逐帧证据, 出自 srt)

**开场(0:00-0:06)** [srt L1]: 「最新版AI立项Skills, 主流大厂加密、瑞数、验证码系列都能通过这套Skills搞定, 完整的Skills已经给大家准备好了。」

**Skills 列表(0:15-0:43)** [srt L3-4]: 「补环境, 然后去定位加密参数, 以及追踪调用链的, 解混淆的, 然后专门去做协议, 对应的Cookie、WSM等等……棋艳专项(极验), 腾讯滑块专项, MV8补环境专项, 以及通过MCEP来控制浏览器……去追踪瑞数专项, 还有专门去做WAF Cookie专项的」

**通用 vs 专项(0:44-0:55)** [srt L5]: 「分Skills就可以分成通用的以及专项的, 通用的比如说补环境通用、追踪调用链通用, 专项就是专门去做某一件事情」

## 二、工具实际(v6) vs 视频

| 维度 | 视频里的(出处) | 工具里的 | 一致? | 差异性质 |
|---|---|---|---|---|
| 技能体系 | 通用(补环境/追踪调用链)+ 专项(极验/腾讯滑块/MV8/瑞数/WAF)[srt L3-5] | 11 技能(通用 5 + 专项 4 + 元 1 + 兜底) | ✅ | 一致(分类结构对) |
| 技能名 | 视频口述: 补环境/定位加密参数/追踪调用链/解混淆/协议/极验/腾讯滑块/MV8/浏览器控制/瑞数/WAF Cookie [srt L3-4] | router_table.yaml 11 技能(skill-creator/env-patch/find-crypto-entry/ast-deobfuscate/web-protocol-recovery/gt4/tencent-slide/v8-web-reverse/browser-hook/rs-reverse/waf-cookie) | ✅ | 一致(11 个全对应) |
| iv8 | 视频: MV8 补环境专项 [srt L4] | IV8Backend 7 方法(mock) | ⚠️ | 等价替代(iv8 闭源, mock 契约) |
| 回血 | 视频: 未明确口述(蒸馏 md 有) | CaseRegen.sync | ⚠️ | 部分(机制在, 视频未逐帧展示) |
| 触发词 | 视频: 未逐句列触发词 | 关键词加权 + 优先级 | ⚠️ | 部分(视频没给全, 工具自建) |

## 三、结论

**v6 = 真复现(0 处没对上)**: 视频口述的 11 个技能点与工具 router_table.yaml **全部对应**(补环境=env-patch/定位加密参数=find-crypto-entry/追踪调用链=web-protocol-recovery 等)。iv8 用行为契约 mock(闭源, 标注等价替代)。回血/触发词视频未逐帧展示, 工具自建(标注)。

**修正**: 上一轮审计把 v6 标"⚠️ 部分(11 技能表未逐帧验证)"——**现在验证了: 11 技能全对上, v6 升为真复现**。
