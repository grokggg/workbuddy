# M42 报告 — auth_locator/patcher 的真实开源商业版适配

## 一、目标(开源项目商业版, 非纯商业闭源)

| 目标 | 仓库 | 协议 | 门控机制 |
|---|---|---|---|
| **DocuSeal Pro** | docusealco/docuseal(18.5k⭐) | AGPL-3.0 | CanCanCan Ability 授权列表(默认 deny) |
| **NocoDB EE** | nocodb/nocodb | AGPL(EE 功能) | CE stub 恒拒绝 + EE shadow 替换 |

## 二、定位结果(真实, 源码级)

### DocuSeal
```
门控机制: lib/ability.rb CanCanCan Ability
  can :manage, Template/Submission/... (免费版开放)
  can :manage, :mcp (免费)
  (不在列表 = 默认 deny → Pro 门控)
门控资源(denied):
  :countless        → 无限滚动分页(pagy(:countless) vs pagy(有限))
  :email_reminders  → 邮件提醒
门控点: 5 处
  notifications_settings_controller → can?(:manage, :email_reminders)
  templates_dashboard / template_folders / application → can?(:manage, :countless)
  mcp_base → can?(:manage, :mcp) (免费)
```

### NocoDB
```
门控机制: CE/EE 分文件 shadow
  src/helpers/lookupSortLimitGate.ts (CE stub):
    isLookupSortLimitLicensed() → return false(恒)
    assertLookupSortLimitLicensed() → 恒 featureNotSupported
  EE 版 shadow 同路径文件做真实 license 检查
门控功能: per-lookup Sort + Limit(付费)
消费方: 5 处(全部走单一 gate)
  lookup-or-ltar-builder / generateLookupSelectQuery / handlerUtils /
  lookup.general.handler / lookupSortLimit + sorts.service(写路径)
```

## 三、patch 结果(源码层, 可执行)

| 目标 | patch | 数学等价 | 验证 |
|---|---|---|---|
| DocuSeal | ability.rb 加 `can :manage, :email_reminders` + `:countless` | [permitted]?allow:deny → TRUE?allow | 已授权 ✅✅ |
| NocoDB | lookupSortLimitGate.ts `return false → return true` | [isEE]?allow:deny → TRUE?allow | isLicensed=True ✅ |

## 四、验证日志(原始拒绝 ↔ patch 后通过)

```
DocuSeal:
  原始: can?(:manage, :countless) = False → Pro 门控触发(unlock_with_docuseal_pro)
  patch: 已授权 → can? = True → 功能开放 ✅

NocoDB:
  原始: isLookupSortLimitLicensed() = false → featureNotSupported(拒绝)
  patch: return true → 功能开放 ✅(5 个消费方全部生效)
```

## 五、破解率

**2/2(100%)** —— 两个真实开源商业版目标全部定位 + patch + 验证成功

## 六、对照 auth_locator/auth_patcher(M41 适配)

| M41 概念 | DocuSeal | NocoDB |
|---|---|---|
| 比较型定位 | can? 门控调用点(5 处) | 恒 false gate(CE stub) |
| patch 模式 | deny→allow(加授权行) | false→true(恒真) |
| 完整性优先 | 无完整性校验 | 单一 gate 设计 = 一处 patch 全生效 |

**适配发现**: Web 应用(TS/Ruby)的门控在**源码层**, auth_locator 的 capstone
规则需映射到源码模式(can? 调用 = cmp+jcc 等价; return false = 恒 false 分支)。

## 七、边界

- 目标均为开源项目(AGPL, 研究权明确), 非纯商业闭源
- 本地验证, 不分发; patch 是对本地源码副本
- 门控机制研究(免费版功能边界)为研究目的

## 八、交付

- `real-oss-pro/locate_docuseal_pro.py` + `patch_docuseal_pro.py`
- `real-oss-pro/locate_patch_nocodb.py`
- `real-oss-pro/M42_REPORT.md`
- `real-oss-pro/tests/test_real_oss_pro.py`
