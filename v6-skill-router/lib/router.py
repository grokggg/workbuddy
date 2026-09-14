# -*- coding: utf-8 -*-
"""
v6-skill-router 核心库

职责:
  - 加载 router_table.yaml 路由表
  - 输入 -> 归一化 -> 逐条规则匹配 -> 路由决策(含冲突消解)
  - iv8 引擎接口: 把 iv8 行为契约封装成可替换的后端(真 iv8 / mock 后端)
  - 案例回血: 把已验证案例写回 references/cases/ + 更新 taxonomy

只依赖 Python 3.8+ 标准库。
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml  # type: ignore
    HAS_YAML = True
except Exception:  # pragma: no cover
    HAS_YAML = False


# ---------------------------------------------------------------- 归一化

def normalize_text(text: str) -> str:
    """归一化: NFKC + 小写 + 去空格/标点。"""
    import unicodedata
    t = unicodedata.normalize("NFKC", text or "").lower()
    # 去所有空白与常见标点(保留中文与字母数字)
    t = re.sub(r"[\s\u3000]+", "", t)
    t = re.sub(r"[，。！？、；：""''（）【】《》〈〉.,!?;:'\"()\[\]{}<>\-_/\\|]", "", t)
    return t


# ---------------------------------------------------------------- 路由表加载

class RouterTableError(Exception):
    pass


def load_router_table(path: str | os.PathLike) -> Dict[str, Any]:
    """加载 YAML 路由表; 无 yaml 时退化为极简 JSON 支持。"""
    p = Path(path)
    if not p.exists():
        raise RouterTableError(f"路由表不存在: {p}")
    raw = p.read_text(encoding="utf-8")
    if HAS_YAML:
        try:
            data = yaml.safe_load(raw)
        except Exception as e:
            raise RouterTableError(f"路由表 YAML 解析失败: {e}") from e
    else:
        # 极简退化: 若文件是 JSON 也能读
        data = json.loads(raw)
    if not isinstance(data, dict) or "skills" not in data:
        raise RouterTableError("路由表缺少 skills 段")
    return data


# ---------------------------------------------------------------- 路由决策

@dataclass
class RouteHit:
    skill_id: str
    trigger_pattern: str
    score: float
    reason: str


@dataclass
class RouteDecision:
    query: str
    hits: List[RouteHit] = field(default_factory=list)
    winner: Optional[str] = None
    fallback: str = "skill-creator"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "hits": [h.__dict__ for h in self.hits],
            "winner": self.winner,
            "fallback": self.fallback,
        }


def _compile_triggers(raw: str) -> List[re.Pattern]:
    """把路由表里的 trigger 表达式编译为正则。

    写法: 以 | 分隔的多个候选, 每个候选独立匹配。
      - "定位.*sign"  -> 正则(含 .* 通配)
      - "极验"        -> 字面包含匹配
    任一候选命中即视为该 trigger 命中。
    """
    pats: List[re.Pattern] = []
    for part in raw.split("|"):
        part = part.strip()
        if not part:
            continue
        if re.search(r"[.*\[\]()?+]", part):
            try:
                pats.append(re.compile(part))
            except re.error:
                continue
        else:
            pats.append(re.compile(re.escape(part)))
    return pats


def route(query: str, table: Dict[str, Any]) -> RouteDecision:
    """核心路由决策。

    流程:
      1. 归一化 query
      2. 对每个 skill 的 triggers 逐一编译匹配, 收集命中(带分值)
      3. 按 priority 排序消解冲突(专项优先)
      4. 无命中 -> fallback
    """
    norm = normalize_text(query)
    dec = RouteDecision(query=query)
    if not norm:
        dec.winner = table.get("default_skill", "skill-creator")
        return dec

    priority = table.get("priority", [])
    skills = table.get("skills", [])

    for skill in skills:
        sid = skill.get("id", "")
        triggers = skill.get("triggers", [])
        hit_pat: Optional[str] = None
        best_score = 0.0
        for trig in triggers:
            for pat in _compile_triggers(trig):
                m = pat.search(norm)
                if m:
                    # 分值: 命中词越长越高(粗略), 基础 0.6
                    score = 0.6 + min(0.4, len(m.group(0)) / 20.0)
                    if score > best_score:
                        best_score = score
                        hit_pat = trig
        if hit_pat is not None:
            dec.hits.append(RouteHit(
                skill_id=sid,
                trigger_pattern=hit_pat,
                score=round(best_score, 3),
                reason=f"命中 trigger: {hit_pat}",
            ))

    if not dec.hits:
        dec.winner = table.get("default_skill", "skill-creator")
        return dec

    # 冲突消解: 按 priority 顺序取第一个命中的
    by_id = {h.skill_id: h for h in dec.hits}
    for sid in priority:
        if sid in by_id:
            dec.winner = sid
            return dec
    # priority 未覆盖时取分值最高
    dec.winner = max(dec.hits, key=lambda h: h.score).skill_id
    return dec


# ---------------------------------------------------------------- iv8 引擎接口

class IV8Backend:
    """iv8 引擎抽象接口。

    真 iv8 是闭源 C++ 扩展(pip install iv8), 本模块不硬依赖它。
    定义统一行为契约, 便于:
      - 有 iv8 时真跑
      - 无 iv8 时用 mock 后端验证路由与回血链路
    """

    name = "base"

    def __init__(self, time_mode: str = "logical") -> None:
        self.time_mode = time_mode
        self._env: Dict[str, Any] = {}
        self._netlog: List[Dict[str, Any]] = []
        self._cookies: Dict[str, str] = {}

    # -- 生命周期
    def __enter__(self) -> "IV8Backend":
        self.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.stop()

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    # -- 核心能力(行为契约, 对应视频/蒸馏文档 7 项)
    def eval(self, js: str) -> Any:
        """执行 JS, 返回结果。"""
        raise NotImplementedError

    def expose(self, data: Any, name: str = "data") -> None:
        """注入数据, JS 侧 window.iv8.<name> 访问。"""
        raise NotImplementedError

    def load_page(self, base_url: str, html: str) -> None:
        """加载 HTML+JS, 按序执行 <script>, 触发 DOMContentLoaded。"""
        raise NotImplementedError

    def advance(self, ms: int) -> None:
        """推进逻辑事件循环(瞬间完成)。"""
        raise NotImplementedError

    def netlog(self) -> List[Dict[str, Any]]:
        """返回执行期间全部 XHR/fetch 的 url/method/headers/body。"""
        raise NotImplementedError

    def get_cookie(self) -> str:
        """返回 document.cookie 字符串。"""
        raise NotImplementedError

    def trusted_input(self, event_type: str, **fields: Any) -> bool:
        """派发 isTrusted=true 的输入事件。"""
        raise NotImplementedError


class MockIV8Backend(IV8Backend):
    """离线 mock 后端: 不依赖 iv8 也能跑通路由+回血链路。

    行为对齐真实 iv8 的可验证部分:
      - navigator.userAgent 有默认指纹
      - window.__iv8__ 隐形命名空间(布尔判定 false, 属性访问正常)
      - eventLoop.advance 瞬间完成
      - netLog 记录 XHR
      - dispatchPointerEvent 返回 isTrusted=true
    """

    name = "mock"

    def __init__(self, time_mode: str = "logical") -> None:
        super().__init__(time_mode)
        self._ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36")
        self._js_state: Dict[str, Any] = {"ready": False, "cookie": ""}

    def start(self) -> None:
        self._js_state = {"ready": False, "cookie": ""}
        self._netlog = []
        self._cookies = {}

    def stop(self) -> None:
        pass

    def eval(self, js: str) -> Any:
        j = js.lower()
        if "navigator.useragent" in j:
            return self._ua
        if "document.cookie" in j:
            return self._js_state.get("cookie", "")
        if "ready" in j and "!!" in j:
            return self._js_state.get("ready", False)
        if "typeof window.__iv8__" in j:
            return "object"  # 隐形命名空间: typeof 可见但布尔判定 false
        if "isTrusted" in j:
            return True
        return None

    def expose(self, data: Any, name: str = "data") -> None:
        self._env[name] = data

    def load_page(self, base_url: str, html: str) -> None:
        # 模拟: 页面内 script 执行后写 cookie + 发 XHR
        import re as _re
        m = _re.search(r"__sign=([A-Za-z0-9]+)", html)
        if m:
            self._js_state["cookie"] = f"__sign={m.group(1)}"
        self._js_state["ready"] = True
        self._netlog.append({
            "url": base_url + "/api/track?sign=abc123&ts=1789000000000",
            "method": "GET",
            "headers": {},
            "body": None,
        })

    def advance(self, ms: int) -> None:
        # 逻辑时间: 瞬间完成
        pass

    def netlog(self) -> List[Dict[str, Any]]:
        return list(self._netlog)

    def get_cookie(self) -> str:
        return self._js_state.get("cookie", "")

    def trusted_input(self, event_type: str, **fields: Any) -> bool:
        return True  # isTrusted=true


def create_backend(name: str = "auto", **kw: Any) -> IV8Backend:
    """后端工厂: auto -> 有 iv8 用真后端, 否则 mock。"""
    if name == "mock":
        return MockIV8Backend(**kw)
    if name == "auto":
        try:
            import iv8  # noqa: F401
            return RealIV8Backend(**kw)
        except Exception:
            return MockIV8Backend(**kw)
    if name == "real":
        return RealIV8Backend(**kw)
    raise ValueError(f"未知后端: {name}")


class RealIV8Backend(IV8Backend):
    """真 iv8 后端(需 pip install iv8)。行为对齐实测契约。"""

    name = "real"

    def __init__(self, time_mode: str = "logical") -> None:
        super().__init__(time_mode)
        self._iv8 = None
        self._ctx = None

    def start(self) -> None:
        from iv8_silent import import_iv8_silent  # 静默导入
        self._iv8 = import_iv8_silent()
        self._ctx = self._iv8.JSContext(time_mode=self.time_mode)
        self._ctx.__enter__()

    def stop(self) -> None:
        if self._ctx is not None:
            self._ctx.__exit__(None, None, None)
        self._ctx = None

    def eval(self, js: str) -> Any:
        return self._ctx.eval(js)

    def expose(self, data: Any, name: str = "data") -> None:
        self._ctx.expose(data, name)

    def load_page(self, base_url: str, html: str) -> None:
        import json as _json
        payload = _json.dumps({"baseURL": base_url, "html": html})
        self._ctx.eval(f"window.__iv8__.page.load({payload})")

    def advance(self, ms: int) -> None:
        self._ctx.eval(f"window.__iv8__.eventLoop.advance({int(ms)})")

    def netlog(self) -> List[Dict[str, Any]]:
        raw = self._ctx.eval("JSON.stringify(window.__iv8__.netLog.entries)")
        try:
            return json.loads(raw)
        except Exception:
            return []

    def get_cookie(self) -> str:
        return self._ctx.eval("document.cookie")

    def trusted_input(self, event_type: str, **fields: Any) -> bool:
        d = dict(fields)
        d.setdefault("clientX", 100)
        d.setdefault("clientY", 150)
        d.setdefault("button", 0)
        d.setdefault("buttons", 1)
        d.setdefault("pointerId", 1)
        d.setdefault("pointerType", "mouse")
        d.setdefault("isPrimary", True)
        payload = json.dumps(d)
        return bool(self._ctx.eval(
            f"window.__iv8__.input.dispatchPointerEvent({payload})"))


# ---------------------------------------------------------------- 案例回血

CASE_DIRS = [
    "signatures",
    "js-challenges",
    "browser-tokens",
    "network-hook-signing",
    "captcha",
]


class CaseRegen:
    """案例回血: 把已验证案例写回 references/cases/ + 更新 taxonomy。

    对应视频 BV13nTj6JEWT 的"案例回写模式":
      1. 选分类目录
      2. 用稳定短 slug 命名
      3. 只复制已验证的最小可复用脚本
      4. 更新 example-taxonomy.md 的目录树与选择规则
    """

    def __init__(self, skill_root: str | os.PathLike) -> None:
        self.skill_root = Path(skill_root)
        self.cases_root = self.skill_root / "references" / "cases"
        self.taxonomy = self.skill_root / "references" / "example-taxonomy.md"
        if self.cases_root.name != "cases":
            self.cases_root = self.skill_root / "references" / "cases"

    def write_case(self, category: str, slug: str, code: str,
                   meta: Optional[Dict[str, Any]] = None) -> Path:
        """写一个案例。category 必须属于 CASE_DIRS, slug 必须短。"""
        if category not in CASE_DIRS:
            raise ValueError(
                f"分类 {category} 不在允许集合 {CASE_DIRS}")
        if not re.fullmatch(r"[a-z0-9][a-z0-9\-]{2,48}", slug):
            raise ValueError(f"slug 不合规: {slug}")
        cat_dir = self.cases_root / category
        cat_dir.mkdir(parents=True, exist_ok=True)
        target = cat_dir / f"{slug}.py"
        header = (
            "# 案例回血自动生成\n"
            f"# slug: {slug}\n"
            f"# category: {category}\n"
            f"# generated_at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"# case_id: {uuid.uuid4().hex[:12]}\n"
        )
        if meta:
            header += "# meta: " + json.dumps(meta, ensure_ascii=False) + "\n"
        target.write_text(header + "\n" + code, encoding="utf-8")
        return target

    def append_taxonomy(self, category: str, slug: str, desc: str) -> None:
        """在 example-taxonomy.md 末尾追加案例说明行。"""
        if not self.taxonomy.exists():
            self.taxonomy.write_text(
                "# 案例分类与选择规则\n\n## 目录树\n\n```\n"
                "references/cases/\n```\n\n## 案例说明\n\n",
                encoding="utf-8")
        line = f"- `{category}/{slug}.py` — {desc}\n"
        with self.taxonomy.open("a", encoding="utf-8") as f:
            f.write(line)

    def sync(self, category: str, slug: str, code: str,
             desc: str, meta: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """一步完成: 写案例 + 更新 taxonomy。"""
        p = self.write_case(category, slug, code, meta)
        self.append_taxonomy(category, slug, desc)
        return {"case": str(p), "taxonomy": str(self.taxonomy)}
