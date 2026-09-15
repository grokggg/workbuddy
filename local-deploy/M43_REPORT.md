# M43 报告 — M41 工具链本地部署包

## 一、交付

`local-deploy/` 本地部署包:
```
local-deploy/
├── install.sh            # 一键安装(capstone/pyelftools/pefile + 系统工具 + 验证)
├── auth_locator.py       # 授权函数定位器(5 类型规则)
├── auth_patcher.py       # patch 原理框架(5 模式 + 骨架)
├── analysis_all.py       # 统一分析入口
├── lib/                  # 5 模块工具链
│   ├── recon_v2.py / analysis_v2.py / llm_engine.py / patcher.py / verifier.py
├── config.json           # 工具配置
└── README.md             # 完整使用流程 + 合法目标示例
```

## 二、验收实测

| 验收项 | 结果 |
|---|---|
| 部署包完整 | ✅ 8 文件(工具 + lib + 配置 + 文档) |
| install.sh 能跑 | ✅ 实测通过(capstone 5.0.7/pyelftools/pefile ✓, 系统工具降级容错 ✓, 自检 ✓) |
| 定位器可用 | ✅ auth_locator 定位 auth-license: cmp eax,0x43 → je @0x400086 |
| patcher 可用 | ✅ auth_patcher 输出 5 模式(比较型 je→EB 2B) |
| README 完整流程 | ✅ 安装/定位/patch 原理/统一分析 + 合法示例 |

## 三、端到端实测(本地)

```bash
./install.sh
# → Python 库全 ✓ + 工具自检 ✓

python3 auth_locator.py auth-license
# → 比较型: cmp eax, 0x43 → je (密码 'C')

python3 auth_patcher.py
# → 比较型: je→EB(2B) / jne→90 90(2B)

python3 analysis_all.py auth-license --out ./out
# → patches: je→jmp @0x8b → 任意输入 OK rc=0
```

## 四、边界(README 中明确)

- 工具链用于保护机制研究与教学
- 合法目标: 自建 crackme / 开源项目商业版(AGPL) / 开源教学授权
- 商业闭源软件(EULA 禁逆向)仅做保护识别(壳/反VM/完整性), 不做破解
- patch 骨架用 {OFFSET}/{OLD}/{NEW} 占位

## 五、交付

- `local-deploy/` 落盘(极狐 repo 内)
- **up-tools-local.zip**(独立打包)
- 推送极狐 + GitHub
