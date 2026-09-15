# up-tools-local — 本地授权机制分析部署包

本地部署的授权机制分析工具链(定位 → patch 原理 → 验证)。

## 一、目录结构

```
up-tools-local/
├── install.sh            # 一键安装依赖 + 验证
├── auth_locator.py       # 授权函数定位器(5 种类型规则)
├── auth_patcher.py       # patch 原理框架(5 种模式 + 骨架)
├── analysis_all.py       # 统一分析入口(格式→保护→校验点→策略)
├── lib/
│   ├── recon_v2.py       # 保护机制识别(壳/反调试/反VM/完整性)
│   ├── analysis_v2.py    # 校验点定位
│   ├── llm_engine.py     # 策略生成
│   ├── patcher.py        # 修改器
│   └── verifier.py       # 验证器
└── config.json           # 工具配置
```

## 二、安装

```bash
./install.sh
```

装什么:
- Python 3.10+ 检查
- pip 包: capstone / pyelftools / pefile
- 系统工具: gdb / objdump / readelf / strings(尽力装, 缺失降级)
- radare2 / rizin(可选)
- 验证: 库导入 + 工具齐全 + lib 可导入

## 三、使用流程

### 1. 定位授权函数

```bash
python3 auth_locator.py /你的目标
```

输出 5 类定位结果:
- 字符串引用型: 授权字符串 → xref
- 比较型: cmp + jcc 校验点
- 签名验证型: RSA/Ed25519 调用
- 时间型: time() 调用
- 在线型: socket/curl 调用

### 2. 查看 patch 模式

```bash
python3 auth_patcher.py
```

输出 5 种授权类型的 patch 模式 + 数学等价 + 副作用 + 最小字节数。

### 3. 统一分析(保护识别)

```bash
python3 analysis_all.py /你的目标 --out ./out
```

自动: 格式识别 → 保护识别 → 校验点定位 → 策略 → patch → 验证。

## 四、目标示例

### 合法示例 1: 自建教学 crackme(M26/M38 同款)

```bash
# 1. 构造教学目标(纯 Python 构造器, 无编译器)
python3 build_auth_crackmes.py    # 生成 auth-license/auth-trial/auth-network

# 2. 定位
python3 auth_locator.py auth-license
# → cmp eax, 0x43 → je (密码 'C')

# 3. 验证 patch 原理(auth_patcher 模式: 比较型 je→EB)
# 4. 用 analysis_all 自动处理
python3 analysis_all.py auth-license --out ./out
# → patch 1 处 → 任意输入 OK
```

### 合法示例 2: 开源项目商业版(DocuSeal Pro, AGPL)

```bash
# 1. 下载源码(官方)
# 2. 定位 Pro 门控
python3 auth_locator.py <能力分析>   # 或专用 locate_docuseal_pro.py
# → lib/ability.rb: :countless/:email_reminders 默认 deny → Pro 门控
# 3. patch 原理: deny → allow(加授权行)
# 4. 验证: can?(:manage, :countless) True
```

## 五、边界说明

- 本工具链用于**保护机制研究与教学**(识别/定位/原理)
- 合法目标: 自建 crackme / 开源项目(AGPL 等) / 开源教学授权
- **商业闭源软件(EULA 禁逆向)的破解不在使用范围**;
  对其仅做保护机制识别(壳/反VM/完整性, recon_v2 支持)
- patch 脚本骨架用 `{OFFSET}/{OLD}/{NEW}` 占位, 用户对合法目标自行填入

## 六、常见问题

**Q: pip 装不上 capstone?**
A: `python3 -m pip install capstone` 或手动下载 wheel。

**Q: 没有 gdb/objdump?**
A: 不影响核心(纯 Python 分析), 动态分析降级用 lib/dynamic_debug.py。

**Q: 定位结果太多?**
A: 比较型 cmp+jcc 是首要候选(最常见), 人工确认后填 patcher 骨架。
