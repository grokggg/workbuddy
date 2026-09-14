# 01-agents-md-universal — AGENTS.md 通杀(40 行人格注入)

> 评论区提到能力: "40 行 AGENTS.md 通杀"。
> 注: 评论区原文无落盘(仓库 Phase H 记录), 按方向描述构建。
> 机制: 40 行 AGENTS.md 模板 + 多框架安装器 + 验证器。

## 一、模块标识
- 编号: 01 / 位置: comment-capabilities/01-agents-md-universal
- 来源: 评论区能力"40 行 AGENTS.md 通杀"(描述方向)

## 二、模块功能
- 输入: 框架名(claude/codex/cursor/generic) + 人格参数
- 输出: **恰好 40 行** AGENTS.md + 安装到目标框架 + 验证

## 三、模块代码
- `lib/engine.py`: 40 行模板 + render() + install() + verify()
- `cli.py`: CLI(安装 + 验证)
- `tests/test_engine.py`: 10 例单测

## 四、模块边界
- 支持 4 框架; 安装到指定 home(测试用临时目录)
- 只写用户目录内, 不越界

## 五、模块接口
- `render(params) -> str`(40 行模板)
- `install(framework, content, home) -> {ok, path}`
- `verify(path, markers) -> {ok, lines, missing}`

## 六、模块测试
```bash
./install.sh            # 10 例全绿
python3 tests/test_engine.py -v
```
实测: 渲染 40 行 / 安装 4 框架 / 验证通过

## 七、模块依赖
- Python 3.8+ (纯标准库)

## 八、集成说明
- 与 v2 注入包同思路(SKILL.md → AGENTS.md)
- 可配合 skill-injection-kit 的多框架路径表
