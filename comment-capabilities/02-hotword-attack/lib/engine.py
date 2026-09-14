#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
02-hotword-attack —— 热词攻击: 热度污染分析 + 检索影响评估

评论区提到能力: "热词攻击"。
机制(中性研究向, 不含真实攻击载荷):
  a) 热度词表加载: 内置常见热词分类(政治/娱乐/科技/民生等), 支持 dict / JSON 文件 / YAML 子集文本
  b) 热度污染分析: 输入文本, 统计热词密度 / 分类分布 / 位置(头部-中部-尾部, front ratio)
  c) 检索影响评估: 学术简化检索模型, 模拟热词对文档排序权重的影响(rank shift / pollution ratio)
  d) 输出结构化结果(dict / JSON)

只依赖 Python 3.8+ 标准库。
"""
from __future__ import annotations

import copy
import json
import os
from typing import Any, Dict, List, Optional, Union

# ------------------------------------------------------------------ 内置热词表

# 常见热词分类(中性示例词, 仅用于机制研究, 不含真实攻击载荷)
DEFAULT_HOTWORDS: Dict[str, List[str]] = {
    "政治": [
        "发布会", "政策", "会议", "讲话", "文件", "落实", "部署", "规划",
    ],
    "娱乐": [
        "演唱会", "综艺", "热搜", "明星", "电影", "官宣", "爆款", "直播",
    ],
    "科技": [
        "人工智能", "大模型", "芯片", "算力", "机器人", "新能源", "数字人", "开源",
    ],
    "民生": [
        "就业", "房价", "医保", "教育", "养老", "补贴", "物价", "消费券",
    ],
    "财经": [
        "股市", "涨停", "基金", "降息", "汇率", "财报", "龙头", "板块",
    ],
    "国际": [
        "峰会", "会谈", "出口管制", "关税", "冲突", "选举", "制裁", "协议",
    ],
}

CATEGORY_ORDER: List[str] = list(DEFAULT_HOTWORDS.keys())

# 头部区间比例: 前 20% 字符视为"头部/标题区"
FRONT_FRACTION: float = 0.2

# 检索影响评估默认参数: 每个热词命中带来的排序加成(学术简化模型)
DEFAULT_BONUS_PER_HIT: float = 0.5


# ------------------------------------------------------------------ 词表加载

def _normalize_hotwords(raw: Any) -> Dict[str, List[str]]:
    """校验并规范化热词表: {分类: [词, ...]}。"""
    if not isinstance(raw, dict) or not raw:
        raise ValueError("热词表必须是非空 dict: {分类: [词, ...]}")
    out: Dict[str, List[str]] = {}
    for cat, words in raw.items():
        if not isinstance(cat, str) or not cat.strip():
            raise ValueError(f"非法分类名: {cat!r}")
        if isinstance(words, str):
            words = [words]
        if not isinstance(words, (list, tuple)):
            raise ValueError(f"分类 {cat!r} 的词必须是 list/tuple/str")
        cleaned: List[str] = []
        for w in words:
            if not isinstance(w, str):
                raise ValueError(f"分类 {cat!r} 含非字符串词: {w!r}")
            w = w.strip()
            if w and w not in cleaned:
                cleaned.append(w)
        if cleaned:
            out[cat.strip()] = cleaned
    if not out:
        raise ValueError("热词表为空(所有分类均无有效词)")
    return out


def _parse_yaml_text(text: str) -> Dict[str, List[str]]:
    """解析 YAML 子集文本(仅支持: 分类: 行 + '- 词' 列表项 + # 注释)。

    示例:
        政治:
          - 发布会
          - 政策
        科技:
          - 芯片
    """
    hotwords: Dict[str, List[str]] = {}
    current: Optional[str] = None
    for lineno, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith(":") and not line.startswith("-"):
            current = line[:-1].strip()
            hotwords.setdefault(current, [])
        elif line.startswith("- "):
            if current is None:
                raise ValueError(
                    f"YAML 子集第 {lineno} 行: 列表项出现在任何分类之前")
            word = line[2:].strip()
            if word:
                hotwords[current].append(word)
        else:
            raise ValueError(f"YAML 子集第 {lineno} 行不支持的格式: {line!r}")
    return hotwords


def _from_json_structure(raw: Any) -> Dict[str, List[str]]:
    """JSON 结构兼容两种形态: {分类: [词]} 或 [{"category":.., "words":[..]}]。"""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        out: Dict[str, List[str]] = {}
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("JSON 列表元素必须是对象 {category, words}")
            if "category" not in item or "words" not in item:
                raise ValueError("JSON 列表元素缺少 category/words 字段")
            out[item["category"]] = item["words"]
        return out
    raise ValueError("热词表 JSON 必须是对象或数组")


def _load_hotwords_from_file(path: Union[str, os.PathLike]) -> Dict[str, List[str]]:
    with open(path, encoding="utf-8") as f:
        content = f.read()
    if str(path).endswith(".json"):
        try:
            raw = json.loads(content)
        except ValueError as e:
            raise ValueError(f"JSON 解析失败: {e}") from e
        return _normalize_hotwords(_from_json_structure(raw))
    return _normalize_hotwords(_parse_yaml_text(content))


def load_hotwords(source: Any = None) -> Dict[str, List[str]]:
    """加载热词表。

    source 取值:
      - None           -> 内置默认词表(返回独立副本)
      - dict           -> {分类: [词, ...]}
      - str / Path     -> 文件路径, 按扩展名区分 JSON / YAML 子集文本
    返回规范化的 {分类: [词, ...]}。
    """
    if source is None:
        return copy.deepcopy(DEFAULT_HOTWORDS)
    if isinstance(source, dict):
        return _normalize_hotwords(source)
    if isinstance(source, (str, os.PathLike)):
        return _load_hotwords_from_file(source)
    raise ValueError(
        f"不支持的词表来源: {type(source).__name__}"
        f" (支持 None / dict / 文件路径)")


# ------------------------------------------------------------------ 热度污染分析

def _match_hotwords(text: str, hotwords: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    """在文本中匹配热词(长词优先 + 区间占用, 避免子串双计)。

    返回按起始位置排序的命中列表:
      [{word, category, start, end}, ...]
    """
    items: List[tuple] = []
    for cat, words in hotwords.items():
        for w in words:
            items.append((w, cat))
    # 长词优先: "人工智能" 先于 "智能" 匹配, 已占用区间不再重复计数
    items.sort(key=lambda x: len(x[0]), reverse=True)
    occupied = [False] * len(text)
    hits: List[Dict[str, Any]] = []
    for word, cat in items:
        start = 0
        while True:
            idx = text.find(word, start)
            if idx == -1:
                break
            span = range(idx, idx + len(word))
            if not any(occupied[i] for i in span):
                for i in span:
                    occupied[i] = True
                hits.append({"word": word, "category": cat,
                             "start": idx, "end": idx + len(word)})
                start = idx + len(word)
            else:
                start = idx + 1
    hits.sort(key=lambda h: h["start"])
    return hits


def analyze(text: str, hotwords: Any = None) -> Dict[str, Any]:
    """热度污染分析: 输入文本, 输出热词密度 / 分类分布 / 位置 / 头部占比。

    返回:
      text_len        文本字符数
      total_hits      热词命中总数(去重叠后)
      unique_hotwords 命中的去重热词数
      density_per_char    每字符热词命中数
      density_per_1000    每千字热词命中数
      by_category     分类分布 {分类: {hits, words}}
      word_stats      逐词统计 {词: {category, hits, first_rel, last_rel}}
      segments        位置分段 {front, middle, back} (前/中/后 20% 字符区)
      front_ratio     头部(前 20%)命中占比, 无命中为 0.0
    """
    if not isinstance(text, str):
        raise TypeError("text 必须是字符串")
    hw = load_hotwords(hotwords)
    n = len(text)
    hits = _match_hotwords(text, hw)
    total = len(hits)

    by_category: Dict[str, Dict[str, Any]] = {}
    word_stats: Dict[str, Dict[str, Any]] = {}
    for h in hits:
        cat = by_category.setdefault(h["category"], {"hits": 0, "words": []})
        cat["hits"] += 1
        if h["word"] not in cat["words"]:
            cat["words"].append(h["word"])
        ws = word_stats.setdefault(
            h["word"],
            {"category": h["category"], "hits": 0,
             "first_rel": None, "last_rel": None})
        ws["hits"] += 1
        rel = h["start"] / n if n else 0.0
        if ws["first_rel"] is None or rel < ws["first_rel"]:
            ws["first_rel"] = round(rel, 6)
        if ws["last_rel"] is None or rel > ws["last_rel"]:
            ws["last_rel"] = round(rel, 6)
    for ws in word_stats.values():
        if ws["first_rel"] is None:
            ws["first_rel"] = 0.0
            ws["last_rel"] = 0.0

    # 位置分段: 头部 = 前 20% 字符, 尾部 = 后 20% 字符
    if n == 0:
        front = middle = back = 0
    else:
        cut = int(n * FRONT_FRACTION)
        front = sum(1 for h in hits if h["start"] < cut)
        back = sum(1 for h in hits if h["start"] >= n - cut)
        middle = total - front - back

    return {
        "text_len": n,
        "total_hits": total,
        "unique_hotwords": len(word_stats),
        "density_per_char": round(total / n, 6) if n else 0.0,
        "density_per_1000": round(total * 1000 / n, 6) if n else 0.0,
        "by_category": by_category,
        "word_stats": word_stats,
        "segments": {"front": front, "middle": middle, "back": back},
        "front_ratio": round(front / total, 6) if total else 0.0,
    }


# ------------------------------------------------------------------ 检索影响评估

def _base_score(query: str, doc: str) -> float:
    """学术简化相关度: 查询字符覆盖率 + 查询整体词频 + 头部位置加成。

    base = 字符覆盖率(0~10) + 查询整体出现次数(封顶 3 次, 每次 2 分) + 头部加成(2)
    仅用于机制研究对比, 不声称等价于任何真实检索算法。
    """
    q = query.strip()
    if not q or not doc:
        return 0.0
    qchars = [c for c in q if not c.isspace()]
    if not qchars:
        return 0.0
    uniq = set(qchars)
    coverage = sum(1.0 for c in uniq if c in doc) / len(uniq)
    freq = min(3, doc.count(q))
    first = doc.find(q)
    pos_bonus = 2.0 if (first != -1 and first / len(doc) < FRONT_FRACTION) else 0.0
    return round(coverage * 10.0 + freq * 2.0 + pos_bonus, 6)


def assess_retrieval(query: str,
                     documents: List[Union[str, Dict[str, Any]]],
                     hotwords: Any = None,
                     bonus_per_hit: float = DEFAULT_BONUS_PER_HIT,
                     top_k: Optional[int] = None) -> Dict[str, Any]:
    """模拟检索命中打分: 评估热词污染对文档排序的影响。

    documents: 元素为 str(文本) 或 {"id":.., "text":..}。
    模型(学术简化):
      final_score = base_score(查询-文档相关度) + 热词命中数 * bonus_per_hit
    对比"无热词加成"与"有热词加成"两套排名, 得到 rank_shift / pollution_ratio。
    """
    if not isinstance(query, str):
        raise TypeError("query 必须是字符串")
    if not isinstance(documents, (list, tuple)):
        raise TypeError("documents 必须是 list/tuple")
    hw = load_hotwords(hotwords)

    rows: List[Dict[str, Any]] = []
    for i, doc in enumerate(documents):
        if isinstance(doc, str):
            doc_id, text = i, doc
        elif isinstance(doc, dict) and "text" in doc:
            doc_id = doc.get("id", i)
            text = doc["text"]
        else:
            raise ValueError(
                f"第 {i} 个文档必须是 str 或 {{id?, text}}, 得到 {type(doc).__name__}")
        if not isinstance(text, str):
            raise TypeError(f"第 {i} 个文档的 text 必须是字符串")

        base = _base_score(query, text)
        a = analyze(text, hw)
        bonus = round(a["total_hits"] * bonus_per_hit, 6)
        rows.append({
            "id": doc_id,
            "preview": text[:60],
            "text_len": a["text_len"],
            "hotword_hits": a["total_hits"],
            "hotword_terms": [w for w, s in a["word_stats"].items() if s["hits"] > 0],
            "base_score": base,
            "hotword_bonus": bonus,
            "final_score": round(base + bonus, 6),
        })

    order_base = sorted(range(len(rows)),
                        key=lambda i: rows[i]["base_score"], reverse=True)
    for rank, i in enumerate(order_base, 1):
        rows[i]["rank_base"] = rank
    order_final = sorted(range(len(rows)),
                         key=lambda i: rows[i]["final_score"], reverse=True)
    for rank, i in enumerate(order_final, 1):
        rows[i]["rank_final"] = rank

    for r in rows:
        r["rank_shift"] = r["rank_base"] - r["rank_final"]  # 正 = 热词使其排名上升
        r["pollution_ratio"] = round(
            r["hotword_bonus"] / r["final_score"], 6) if r["final_score"] > 0 else 0.0

    shown = rows if top_k is None else rows[:top_k]
    ranking = sorted(shown, key=lambda r: r["final_score"], reverse=True)

    shifted = [r for r in rows if r["rank_shift"] != 0]
    return {
        "model": "academic-simplified",
        "query": query,
        "params": {"bonus_per_hit": bonus_per_hit, "front_fraction": FRONT_FRACTION},
        "ranking": ranking,
        "summary": {
            "documents": len(rows),
            "documents_with_shift": len(shifted),
            "max_rank_shift": max((abs(r["rank_shift"]) for r in rows),
                                  default=0),
            "avg_pollution_ratio": round(
                sum(r["pollution_ratio"] for r in rows) / len(rows), 6) if rows else 0.0,
        },
    }


# ------------------------------------------------------------------ CLI

def _print_analyze(args: Any) -> int:
    try:
        if args.text is None and args.file is None:
            print("错误: analyze 需要位置参数 text 或 --file")
            return 2
        if args.text is not None and args.file is not None:
            print("错误: text 与 --file 只能二选一")
            return 2
        text = args.text if args.text is not None else \
            open(args.file, encoding="utf-8").read()
        hw = load_hotwords(args.hotwords)
        result = analyze(text, hw)
    except (ValueError, TypeError, OSError) as e:
        print(f"错误: {e}")
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print(f"文本长度      : {result['text_len']} 字符")
    print(f"热词命中总数  : {result['total_hits']} (去重词 {result['unique_hotwords']})")
    print(f"密度(每千字)  : {result['density_per_1000']}")
    print(f"位置分段      : 头部 {result['segments']['front']} / "
          f"中部 {result['segments']['middle']} / 尾部 {result['segments']['back']}")
    print(f"头部占比      : {result['front_ratio']:.1%} (前 {int(FRONT_FRACTION * 100)}% 字符)")
    for cat, st in result["by_category"].items():
        print(f"  [{cat}] {st['hits']} 次: {', '.join(st['words'])}")
    return 0


def _print_retrieve(args: Any) -> int:
    try:
        docs: List[Union[str, Dict[str, Any]]] = []
        if args.docs:
            docs.extend(args.docs)
        if args.docs_file:
            with open(args.docs_file, encoding="utf-8") as f:
                content = f.read()
            if str(args.docs_file).endswith(".json"):
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    docs.extend(parsed)
                else:
                    raise ValueError("--docs-file JSON 必须是数组")
            else:
                docs.extend(line for line in content.splitlines() if line.strip())
        if not docs:
            print("错误: 至少提供一个文档(--docs 或 --docs-file)")
            return 2
        result = assess_retrieval(args.query, docs,
                                  hotwords=args.hotwords,
                                  bonus_per_hit=args.bonus,
                                  top_k=args.top_k)
    except (ValueError, TypeError, OSError) as e:
        print(f"错误: {e}")
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print(f"查询    : {result['query']}")
    print(f"模型    : {result['model']} (bonus/hit={result['params']['bonus_per_hit']})")
    for r in result["ranking"]:
        shift = r["rank_shift"]
        mark = " ↑" if shift > 0 else (" ↓" if shift < 0 else "")
        print(f"  #{r['rank_final']} id={r['id']} base={r['base_score']:.2f} "
              f"+bonus={r['hotword_bonus']:.2f} = {r['final_score']:.2f} "
              f"(原第 {r['rank_base']} 名, shift {shift:+d}{mark}) "
              f"热词命中 {r['hotword_hits']} pollution={r['pollution_ratio']:.0%}")
        if r["hotword_terms"]:
            print(f"     热词: {', '.join(r['hotword_terms'])}")
    s = result["summary"]
    print(f"汇总    : {s['documents']} 篇文档, {s['documents_with_shift']} 篇排名被热词改变, "
          f"最大位移 {s['max_rank_shift']}, 平均污染占比 {s['avg_pollution_ratio']:.1%}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    p = argparse.ArgumentParser(
        prog="hotword-attack",
        description="热词攻击: 热度污染分析 + 检索影响评估"
                    "(机制研究向, 不含真实攻击载荷)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("analyze", help="热度污染分析: 输入文本, 输出热词密度/分布/位置")
    pa.add_argument("text", nargs="?", default=None, help="待分析文本")
    pa.add_argument("--file", default=None, help="从文件读取文本")
    pa.add_argument("--hotwords", default=None,
                    help="自定义热词表(json/yaml 文件, 默认内置)")
    pa.add_argument("--json", action="store_true", help="输出 JSON")

    pr = sub.add_parser("retrieve", help="检索影响评估: 模拟热词对排序权重的影响")
    pr.add_argument("--query", required=True, help="查询")
    pr.add_argument("--docs", nargs="+", default=None, help="候选文档(命令行直给)")
    pr.add_argument("--docs-file", default=None,
                    help="候选文档文件(纯文本每行一篇, 或 .json 数组)")
    pr.add_argument("--hotwords", default=None, help="自定义热词表")
    pr.add_argument("--bonus", type=float, default=DEFAULT_BONUS_PER_HIT,
                    help=f"每个热词命中的排序加成(默认 {DEFAULT_BONUS_PER_HIT})")
    pr.add_argument("--top-k", type=int, default=None, dest="top_k",
                    help="只展示前 k 篇(排名仍在全量上计算)")
    pr.add_argument("--json", action="store_true", help="输出 JSON")

    args = p.parse_args(argv)
    if args.cmd == "analyze":
        return _print_analyze(args)
    if args.cmd == "retrieve":
        return _print_retrieve(args)
    p.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
