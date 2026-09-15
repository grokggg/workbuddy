#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v1-console —— 四模型统一控制台核心库

子步骤 1: 后端抽象层(适配器模式)
  Backend 抽象接口: chat() / health() / name / capabilities
  4 后端: 3 个自建本地 HTTP(真实 socket 往返) + 1 个 Mock 兜底

子步骤 2: 路由与切换(显式优先 + 失败回退 + 决策日志)
子步骤 3: 对比模式(并发调用 + 并排结果)
子步骤 4: 会话与回退(按后端隔离上下文 + 失败回退 + 日志落盘)
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import random
import socket
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


# ════════════════════════════════════════════════════════════
# 子步骤 1: 后端抽象层
# ════════════════════════════════════════════════════════════

class Backend:
    """统一后端接口(适配器模式基类)。"""
    name: str = "base"
    capabilities: List[str] = ["chat"]

    def chat(self, messages: List[Dict[str, str]]) -> str:
        raise NotImplementedError

    def health(self) -> bool:
        raise NotImplementedError


class MockBackend(Backend):
    """Mock 兜底: 本地规则回复, 永远可用。"""
    name = "mock"
    capabilities = ["chat", "offline"]

    def chat(self, messages: List[Dict[str, str]]) -> str:
        q = messages[-1]["content"] if messages else ""
        return f"[mock] 收到: {q} (规则回复)"

    def health(self) -> bool:
        return True


class LocalHTTPBackend(Backend):
    """自建本地 HTTP 后端(真实 socket/HTTP 往返)。

    每个实例启动一个本地 HTTP server(threading), 对 POST /chat
    返回固定的模型风格回复。health() 通过真实 HTTP GET 探测。
    """

    def __init__(self, name: str, style: str, port: int):
        self.name = name
        self.style = style
        self.port = port
        self._server: Optional[threading.Thread] = None
        self._srv = None
        self._start()

    # ── HTTP server ──
    def _handle(self, conn):
        try:
            req = b""
            while b"\r\n\r\n" not in req:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                req += chunk
            # 解析 body
            body = req.split(b"\r\n\r\n")[-1] if b"\r\n\r\n" in req else b""
            if b"GET /health" in req:
                resp = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"
            elif b"POST /chat" in req:
                try:
                    data = json.loads(body.decode() or "{}")
                    q = data.get("messages", [{}])[-1].get("content", "")
                except Exception:
                    q = ""
                out = self._respond(q).encode()
                resp = (f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                        f"Content-Length: {len(out)}\r\n\r\n").encode() + out
            else:
                resp = b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n"
            conn.sendall(resp)
        except Exception:
            pass
        finally:
            conn.close()

    def _respond(self, q: str) -> str:
        return json.dumps({"role": "assistant",
                           "content": f"[{self.name}] {self.style}: {q}"},
                          ensure_ascii=False)

    def _start(self):
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(("127.0.0.1", self.port))
        self._srv.listen(8)
        self._server = threading.Thread(target=self._accept_loop, daemon=True)
        self._server.start()

    def _accept_loop(self):
        while True:
            try:
                conn, _ = self._srv.accept()
                threading.Thread(target=self._handle, args=(conn,), daemon=True).start()
            except Exception:
                break

    def stop(self):
        try:
            self._srv.close()
        except Exception:
            pass

    # ── 统一接口 ──
    def chat(self, messages: List[Dict[str, str]]) -> str:
        data = json.dumps({"messages": messages}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/chat", data=data,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())["content"]

    def health(self) -> bool:
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}/health", timeout=3) as r:
                return r.status == 200
        except Exception:
            return False


def create_backends(ports: Optional[List[int]] = None) -> Dict[str, Backend]:
    """创建 4 后端: 3 本地 HTTP + 1 Mock。"""
    ports = ports or [18101, 18102, 18103]
    backends: Dict[str, Backend] = {}
    for name, style, port in zip(
            ["gpt-local", "claude-local", "deepseek-local"],
            ["GPT 风格", "Claude 风格", "DeepSeek 风格"], ports):
        backends[name] = LocalHTTPBackend(name, style, port)
    backends["mock"] = MockBackend()
    return backends


# ════════════════════════════════════════════════════════════
# 子步骤 2: 路由与切换
# ════════════════════════════════════════════════════════════

@dataclass
class RouteDecision:
    backend: str
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class Router:
    """路由: 显式选择优先; 失败按优先级回退; 记录决策日志。"""

    def __init__(self, backends: Dict[str, Backend],
                 priority: Optional[List[str]] = None,
                 log_dir: Optional[str] = None):
        self.backends = backends
        self.priority = priority or list(backends.keys())
        self.log_dir = log_dir
        self.decisions: List[RouteDecision] = []
        self.log_dir and Path(self.log_dir).mkdir(parents=True, exist_ok=True)

    def _log(self, d: RouteDecision):
        self.decisions.append(d)
        if self.log_dir:
            p = Path(self.log_dir) / "router.log"
            with open(p, "a") as f:
                f.write(f"{d.timestamp} → {d.backend} ({d.reason})\n")

    def route(self, query: str, backend: Optional[str] = None) -> tuple[str, str]:
        """返回 (backend_name, response)。显式 → 回退。"""
        if backend:
            if backend in self.backends:
                b = self.backends[backend]
                try:
                    resp = b.chat([{"role": "user", "content": query}])
                    d = RouteDecision(backend, "explicit")
                    self._log(d)
                    return backend, resp
                except Exception as e:
                    d = RouteDecision(backend, f"explicit-fail:{e}")
                    self._log(d)
                    # fall through 到回退
            else:
                d = RouteDecision(backend, "unknown-backend")
                self._log(d)
                return "error", f"未知后端: {backend}"
        # 自动回退
        for name in self.priority:
            b = self.backends[name]
            try:
                if b.health():
                    resp = b.chat([{"role": "user", "content": query}])
                    d = RouteDecision(name, "auto-healthy")
                    self._log(d)
                    return name, resp
            except Exception:
                continue
        d = RouteDecision("mock", "auto-fallback-all-fail")
        self._log(d)
        return "mock", self.backends["mock"].chat([{"role": "user", "content": query}])


# ════════════════════════════════════════════════════════════
# 子步骤 3: 对比模式
# ════════════════════════════════════════════════════════════

def compare(backends: Dict[str, Backend], names: List[str],
            query: str) -> List[Dict[str, Any]]:
    """并发调用多后端, 返回并排结果(含延迟/成功)。"""
    results: List[Dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(names)) as ex:
        fut = {}
        for n in names:
            if n not in backends:
                results.append({"backend": n, "response": "未知后端",
                                "latency_ms": 0, "success": False})
                continue
            fut[ex.submit(_call_one, backends[n], query)] = n
        for f, n in fut.items():
            results.append({"backend": n, **f.result()})
    # 保持输入顺序
    order = {n: i for i, n in enumerate(names)}
    results.sort(key=lambda r: order.get(r["backend"], 99))
    return results


def _call_one(b: Backend, q: str) -> Dict[str, Any]:
    t0 = time.time()
    try:
        resp = b.chat([{"role": "user", "content": q}])
        return {"response": resp, "latency_ms": int((time.time() - t0) * 1000),
                "success": True}
    except Exception as e:
        return {"response": f"失败: {e}", "latency_ms": int((time.time() - t0) * 1000),
                "success": False}


# ════════════════════════════════════════════════════════════
# 子步骤 4: 会话与回退
# ════════════════════════════════════════════════════════════

class SessionManager:
    """会话: 按后端隔离上下文 + 失败回退 + 日志落盘可回放。"""

    def __init__(self, router: Router, session_dir: Optional[str] = None):
        self.router = router
        self.session_dir = session_dir
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.session_dir and Path(self.session_dir).mkdir(parents=True, exist_ok=True)

    def new_session(self, backend: Optional[str] = None) -> str:
        sid = f"s{int(time.time())}{random.randint(100, 999)}"
        self.sessions[sid] = {"backend": backend or "auto", "history": [],
                              "created": datetime.now().isoformat()}
        self._save(sid)
        return sid

    def _save(self, sid: str):
        if self.session_dir:
            p = Path(self.session_dir) / f"{sid}.json"
            with open(p, "w") as f:
                json.dump(self.sessions[sid], f, ensure_ascii=False)

    def _load(self, sid: str) -> bool:
        """从磁盘加载会话(跨进程持久)。"""
        if sid in self.sessions:
            return True
        if self.session_dir:
            p = Path(self.session_dir) / f"{sid}.json"
            if p.exists():
                with open(p) as f:
                    self.sessions[sid] = json.load(f)
                return True
        return False

    def chat(self, sid: str, query: str, backend: Optional[str] = None) -> Dict[str, Any]:
        if not self._load(sid):
            return {"error": f"会话不存在: {sid}"}
        s = self.sessions[sid]
        target = backend or s.get("backend") or "auto"
        # 追加到会话历史(上下文隔离: 按后端)
        history = s.get("history", [])
        history.append({"role": "user", "content": query})
        name, resp = self.router.route(query, target if target != "auto" else None)
        history.append({"role": "assistant", "content": resp})
        s["history"] = history
        s["backend"] = name  # 记录实际路由
        self._save(sid)
        # 日志落盘(可回放)
        if self.session_dir:
            p = Path(self.session_dir) / f"{sid}.jsonl"
            with open(p, "a") as f:
                f.write(json.dumps({"query": query, "backend": name,
                                    "response": resp,
                                    "ts": datetime.now().isoformat()},
                                   ensure_ascii=False) + "\n")
        return {"session": sid, "backend": name, "response": resp,
                "history_len": len(history)}


# ════════════════════════════════════════════════════════════
# 子步骤 5: 统一门面
# ════════════════════════════════════════════════════════════

class Console:
    """统一控制台门面: list / chat / compare / session / health。"""

    def __init__(self, work_dir: str):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.backends = create_backends()
        self.router = Router(self.backends,
                             log_dir=str(self.work_dir / "logs"))
        self.sessions = SessionManager(self.router,
                                       session_dir=str(self.work_dir / "sessions"))

    def list_backends(self) -> List[Dict[str, Any]]:
        out = []
        for name, b in self.backends.items():
            out.append({"name": name, "capabilities": b.capabilities,
                        "health": b.health()})
        return out

    def chat(self, query: str, backend: Optional[str] = None) -> Dict[str, Any]:
        name, resp = self.router.route(query, backend)
        return {"backend": name, "response": resp}

    def compare(self, names: List[str], query: str) -> List[Dict[str, Any]]:
        return compare(self.backends, names, query)

    def health(self) -> Dict[str, bool]:
        return {n: b.health() for n, b in self.backends.items()}
