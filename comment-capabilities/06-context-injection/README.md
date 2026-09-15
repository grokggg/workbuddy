# 06-context-injection — 全局人格 + 篡改上下文

## 1. 模块标识
- 来源: 评论区 SOURCE.md 行 2-3
- 行 2: 「全局写人格 项目写样例 fable都能绕过」
- 行 3: 「就是篡改上下文」

## 2. 模块功能
全局 AGENTS.md 写人格 + 项目级写样例, 篡改模型上下文(两层结构)。

## 3. 模块代码
- cli.py — ContextInjectionEngine(global_persona / project_sample / render / write)
- tests/test_engine.py — 5 例

## 4. 模块边界
- 支持: 任意 AGENTS.md 框架(Claude Code/Codex 通用)
- 异常: 无真实模型时 dry-run 默认
- 已知限制: 不交付绕过具体平台风控载荷

## 5. 模块接口
- `--persona <名>` 全局人格
- `--sample <内容>` 项目样例
- `--write` 实际写入(默认 dry-run)

## 6. 模块测试
5 例: global_persona/project_sample/render/write(dry+real) 全绿

## 7. 模块依赖
Python 3.8+ 标准库

## 8. 集成说明
```bash
python3 cli.py --persona "助手" --sample "输入→输出" --write
```
