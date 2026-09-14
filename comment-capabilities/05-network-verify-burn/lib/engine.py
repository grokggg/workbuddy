#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
05-network-verify-burn —— 网络验证 + 用完即焚(服务端按需加载 + 用完即删)

评论区提到能力: "网络验证+用完即焚"。
机制(中性描述): 一次性令牌签发 -> 验证时服务端按需加载内容 -> 使用后烧毁
(令牌立即失效 + 内容从缓存删除)。

注: 学术向服务端设计(令牌生命周期 / 按需加载 / 状态审计研究),
    不用于真实绕过授权或付费墙。

只依赖 Python 3.8+ 标准库。
"""
from __future__ import annotations

import secrets
import time
from typing import Any, Callable, Dict, List, Optional

ACTIVE = "active"    # 令牌状态: 活跃
BURNED = "burned"    # 令牌状态: 已烧毁


class BurnError(Exception):
    """令牌生命周期错误(非法 key / 非法 token 等编程错误)。

    业务失败(未找到/过期/重复使用/已烧毁)统一以 {ok: False, reason: ...}
    字典返回, 便于 CLI 与调用方直接展示。
    """


class BurnServer:
    """模拟服务端: 一次性令牌 + 按需加载 + 用完即焚。

    存储: 默认内存 dict, 可注入任意 mapping 作为存储层, 结构:
        store = {"tokens": {token: 记录}, "contents": {key: 内容}}

    加载: 内容默认在 verify 时才按需加载(loader(key) 惰性调用),
        烧毁时把缓存内容一并删除(用完即删)。

    注入点(全部可替换):
        store         存储层(dict 或任意 mapping)
        loader        Callable[[key], content] 按需加载器
        token_factory Callable[[], str]        令牌生成器
        now_fn        Callable[[], float]      时钟(测试用假时钟)
    """

    def __init__(
        self,
        store: Optional[Dict[str, Any]] = None,
        loader: Optional[Callable[[str], Any]] = None,
        ttl: float = 300.0,
        token_factory: Optional[Callable[[], str]] = None,
        now_fn: Optional[Callable[[], float]] = None,
    ) -> None:
        self._store = store if store is not None else {"tokens": {}, "contents": {}}
        self._loader = loader
        self._ttl = ttl
        self._token_factory = token_factory or (
            lambda: secrets.token_urlsafe(16)
        )
        self._now = now_fn or time.time

    # ------------------------------------------------------------ 内部
    def _tokens(self) -> Dict[str, Dict[str, Any]]:
        return self._store["tokens"]

    def _contents(self) -> Dict[str, Any]:
        return self._store["contents"]

    def _now_ts(self) -> float:
        return float(self._now())

    # ------------------------------------------------------------ (a) 签发
    def issue_token(
        self,
        key: str,
        ttl: Optional[float] = None,
        content: Any = None,
    ) -> Dict[str, Any]:
        """签发一次性令牌(带过期)。

        - key:     内容标识, 后续 verify 按此按需加载
        - ttl:     有效秒数, 缺省用服务器默认
        - content: 显式提供内容则直接入缓存;
                   不提供则必须配置 loader, 内容在 verify 时按需加载
        返回: {ok, token, key, issued_at, expires_at}
        """
        if not key or not isinstance(key, str):
            raise BurnError("key 必须为非空字符串")
        token = self._token_factory()
        issued_at = self._now_ts()
        expires_at = issued_at + (ttl if ttl is not None else self._ttl)
        rec = {
            "token": token,
            "key": key,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "status": ACTIVE,
            "burned_at": None,
            "uses": 0,
        }
        self._tokens()[token] = rec
        if content is not None:
            self._contents()[key] = content
        return {
            "ok": True,
            "token": token,
            "key": key,
            "issued_at": issued_at,
            "expires_at": expires_at,
        }

    # ------------------------------------------------------------ (b) 验证
    def verify(self, token: str) -> Dict[str, Any]:
        """验证令牌 + 返回临时加载内容(按需加载)。

        一次性语义: 验证成功后 uses 计数 +1, 再次验证被拒绝
        (reason=already_used), 直到 burn 正式烧毁。
        返回: {ok, token, key, content, expires_at}
            或 {ok: False, reason: not_found|burned|expired|
                already_used|no_content|load_failed}
        """
        rec = self._tokens().get(token)
        if rec is None:
            return {"ok": False, "reason": "not_found", "token": token}
        if rec["status"] != ACTIVE:
            return {"ok": False, "reason": "burned", "token": token}
        if self._now_ts() > rec["expires_at"]:
            return {"ok": False, "reason": "expired", "token": token}
        if rec["uses"] > 0:
            return {"ok": False, "reason": "already_used", "token": token}

        key = rec["key"]
        if key not in self._contents():
            if self._loader is None:
                return {"ok": False, "reason": "no_content", "token": token}
            try:
                self._contents()[key] = self._loader(key)  # 按需加载
            except Exception:
                return {"ok": False, "reason": "load_failed", "token": token}

        rec["uses"] += 1
        return {
            "ok": True,
            "token": token,
            "key": key,
            "content": self._contents()[key],
            "expires_at": rec["expires_at"],
        }

    # ------------------------------------------------------------ (c) 烧毁
    def burn(self, token: str) -> Dict[str, Any]:
        """使用后立即烧毁: 令牌失效 + 内容删除。

        返回: {ok, token, key, content_deleted}
            或 {ok: False, reason: not_found|already_burned}
        """
        rec = self._tokens().get(token)
        if rec is None:
            return {"ok": False, "reason": "not_found", "token": token}
        if rec["status"] == BURNED:
            return {"ok": False, "reason": "already_burned", "token": token}
        rec["status"] = BURNED
        rec["burned_at"] = self._now_ts()
        key = rec["key"]
        deleted = self._contents().pop(key, None)  # 用完即删
        return {
            "ok": True,
            "token": token,
            "key": key,
            "content_deleted": deleted is not None,
        }

    # ------------------------------------------------------------ (d) 审计
    def audit(self) -> Dict[str, Any]:
        """状态审计: 活跃 / 已烧毁令牌列表(按签发时间排序)。"""
        active: List[Dict[str, Any]] = []
        burned: List[Dict[str, Any]] = []
        for rec in self._tokens().values():
            item = {
                "token": rec["token"],
                "key": rec["key"],
                "issued_at": rec["issued_at"],
                "expires_at": rec["expires_at"],
                "uses": rec["uses"],
                "status": rec["status"],
                "burned_at": rec["burned_at"],
            }
            (active if rec["status"] == ACTIVE else burned).append(item)
        active.sort(key=lambda r: r["issued_at"])
        burned.sort(key=lambda r: r["issued_at"])
        return {
            "active": active,
            "burned": burned,
            "active_count": len(active),
            "burned_count": len(burned),
        }

    def active_tokens(self) -> List[str]:
        """活跃令牌 token 列表。"""
        return [r["token"] for r in self._tokens().values()
                if r["status"] == ACTIVE]

    def burned_tokens(self) -> List[str]:
        """已烧毁令牌 token 列表。"""
        return [r["token"] for r in self._tokens().values()
                if r["status"] == BURNED]
