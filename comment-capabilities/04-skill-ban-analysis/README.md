# 04-skill-ban-analysis — skill 封号机制(检测点分析 + 规避成本评估)

> 评论区提到能力: "skill 绕过包封号"。
> 机制(学术研究向): 分析 agent 框架对 skill 目录注入的检测能力与规避成本。

## 一、模块标识
- 编号: 04 / 位置: comment-capabilities/04-skill-ban-analysis

## 二、模块功能
- 输入: skill 目录路径
- 输出: 检测点风险分 + 规避成本评估报告

## 三、模块代码
- `lib/engine.py`: BanAnalyzer(检测点清单 + 扫描 + 成本评估)
- `cli.py`: scan 子命令
- `tests/test_engine.py`: 11 例单测

## 四、模块边界
- 学术分析, 不含真实规避载荷; 测试本地 mock

## 五、模块接口
- `BanAnalyzer.scan(skill_dir) -> {results[], avg_risk}`
- `BanAnalyzer.evade_cost(scan) -> {cost_level, total_cost}`
- `BanAnalyzer.report(skill_dir) -> {scan, cost}`

## 六、模块测试
```bash
./install.sh            # 11 例全绿
python3 tests/test_engine.py -v
```
实测: 6 检测点 / 平均风险 0.883 / 规避成本 高(14/18)

## 七、模块依赖
- Python 3.8+ (纯标准库)

## 八、集成说明
- 检测点清单可与 v2 注入包/防御侧 t06(目录基线)对照
- 供防御研究: 知道检测点才能补防御
