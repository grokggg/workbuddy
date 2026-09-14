# 02-hotword-attack — 热词攻击(热度污染分析 + 检索影响评估)

> 评论区提到能力: "热词攻击"。
> 机制(中性研究向): 热门话题词可被用来影响 LLM 检索/上下文 —— 本模块量化分析
> "文本中热词的密度/分布/位置" 与 "热词对模拟检索排序权重的影响"。
> 不含真实攻击载荷, 纯 Python 3.8+ 标准库, 测试本地 mock(无网络)。

## 一、模块标识
- 编号: 02 / 位置: comment-capabilities/02-hotword-attack
- 语言: Python 3.8+ / 仅标准库 / 输出简体中文

## 二、模块功能
- 输入: 一段文本(analyze) 或 查询 + 若干候选文档(retrieve)
- 输出(结构化 dict / JSON):
  1. 热度污染分析: 热词命中总数 / 每千字密度 / 分类分布 / 逐词首末位置 / 头部-中部-尾部位置分段 / 头部占比
  2. 检索影响评估: 每篇文档的基础相关度分 + 热词加成后的最终分, 两套排名对比(rank_shift)、污染占比(pollution_ratio)、汇总统计

## 三、模块代码

### 3.1 词表加载 `lib/engine.py: load_hotwords()`
- 内置 6 类常见热词(政治/娱乐/科技/民生/财经/国际), 每类 8 个中性示例词
- 来源: `None`(内置副本) / `dict` / 文件路径(`.json` 自动走 JSON 解析, 其余按 YAML 子集文本解析)
- 规范化: 去空白、去重、单字符串自动转列表; 非法词表抛 `ValueError`

```python
def load_hotwords(source=None) -> dict:
    # None -> 内置; dict -> {分类: [词,...]}; str/Path -> 文件(.json / YAML 子集)
```

### 3.2 热度污染分析 `lib/engine.py: analyze()`
- 匹配: 长词优先 + 已占用区间不双计("人工智能" 命中后不再被 "智能" 重复计数)
- 密度: `density_per_char` / `density_per_1000`
- 分布: `by_category`(分类命中数+命中的词) / `word_stats`(逐词 hits、first_rel、last_rel)
- 位置: 头部 = 前 20% 字符区(`FRONT_FRACTION`), 尾部 = 后 20%, 输出 `segments` + `front_ratio`

### 3.3 检索影响评估 `lib/engine.py: assess_retrieval()`
- 学术简化模型(仅机制对比, 不声称等价真实检索算法):
  - `base_score` = 查询字符覆盖率(0~10) + 查询整体词频(封顶 3 次 × 2 分) + 头部位置加成(2)
  - `final_score` = `base_score` + 热词命中数 × `bonus_per_hit`(默认 0.5)
- 输出: 两套排名(无加成/有加成)的 `rank_base`/`rank_final`/`rank_shift`、`pollution_ratio`、`summary`(位移文档数/最大位移/平均污染占比)

## 四、模块边界
- 机制研究向: 词表为中性示例词, 不含真实攻击载荷; 不访问网络
- 匹配为子串匹配, 不做分词/语义扩展; 检索模型为学术简化版
- 文档元素支持 `str` 或 `{"id":.., "text":..}`; 非法输入抛 `TypeError`/`ValueError`
- `top_k` 只影响展示, 排名始终在全量文档上计算

## 五、模块接口
- `load_hotwords(source=None) -> {分类: [词,...]}`
- `analyze(text, hotwords=None) -> {text_len, total_hits, unique_hotwords, density_per_char, density_per_1000, by_category, word_stats, segments, front_ratio}`
- `assess_retrieval(query, documents, hotwords=None, bonus_per_hit=0.5, top_k=None) -> {model, query, params, ranking, summary}`
- CLI: `python3 cli.py analyze [TEXT|--file] [--hotwords] [--json]` / `python3 cli.py retrieve --query Q --docs ...|--docs-file F [--bonus] [--top-k] [--json]`

## 六、模块测试
见 tests/test_engine.py(31 例, 全部离线/本地 mock): 词表加载(6) / 密度(4) / 分布(3) / 位置(3) / 检索影响(7) / 边界与空输入(8)

## 七、模块依赖
- Python 3.8+ 标准库(argparse/json/os/pathlib/unittest), 无第三方依赖

## 八、集成说明
- 与 01-agents-md-universal 同结构(engine.py + tests/test_engine.py + cli.py + install.sh + README.md)
- 检索影响评估的输出可被下游拿来: 检测"热词堆砌"文档在检索结果中的不当上升(pollution_ratio 阈值告警), 或作为 LLM 检索上下文的前置筛查信号
- 自定义词表可通过 `--hotwords`/`hotwords=` 注入, 便于按领域扩展分类
