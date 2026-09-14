#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
03-relay-manager —— 中转站管理(多端点管理 + 切换 + 健康检查)

评论区提到能力: "多 LLM API 端点(中转站)的管理: 注册 / 切换 / 健康检查"。
机制: RelayManager 集中管理多个 relay 端点(base_url / api_key_env / model / 权重),
     select() 按健康度/权重/轮询切换, check() 通过可注入的 transport 探活,
     配置以 JSON 持久化(只存 API key 的环境变量名, 不存明文)。

transport 抽象: BaseTransport(接口) + FakeTransport(离线测试) + UrllibTransport(真联网)。

只依赖 Python 3.8+ 标准库。
"""
from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

CONFIG_VERSION = 1
DEFAULT_TIMEOUT = 5.0
DEFAULT_USER_AGENT = "relay-manager/1.0 (stdlib urllib)"


class RelayError(ValueError):
    """端点管理领域错误(重名 / 非法参数 / 未知端点 / 配置错误)。"""


# ================================================================ transport 抽象

class BaseTransport:
    """探活 transport 抽象接口。

    probe() 返回统一字典:
        {"ok": bool, "status": int|None, "latency_ms": float, "error": str|None}
    """

    def probe(self, base_url: str, timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
        raise NotImplementedError


class FakeTransport(BaseTransport):
    """离线探活 transport: 按 base_url 匹配预设行为, 不联网。

    用于单元测试/离线演示。构造:
        routes:  {base_url: {"ok": bool, "status": int, "latency_ms": float, "error": str|None}}
        default: 未匹配 base_url 时的默认行为(默认全部 200 存活)
        fail_all: True 时所有探活都失败(模拟全网段故障)
    """

    def __init__(self,
                 routes: Optional[Dict[str, Dict[str, Any]]] = None,
                 default: Optional[Dict[str, Any]] = None,
                 fail_all: bool = False) -> None:
        self.routes = dict(routes or {})
        self.default = default or {"ok": True, "status": 200, "latency_ms": 5.0}
        self.fail_all = fail_all
        self.probe_count = 0

    def probe(self, base_url: str, timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
        self.probe_count += 1
        if self.fail_all:
            return {"ok": False, "status": None,
                    "latency_ms": float(timeout) * 1000.0,
                    "error": "FakeTransport: fail_all 模拟全部不可达"}
        behavior = self.routes.get(base_url, self.default)
        return {
            "ok": bool(behavior.get("ok", True)),
            "status": behavior.get("status"),
            "latency_ms": float(behavior.get("latency_ms", 0.0)),
            "error": behavior.get("error"),
        }


class UrllibTransport(BaseTransport):
    """真联网探活: 用 urllib 请求 base_url。

    健康判定: 收到任何 HTTP 响应且 status < 500 视为存活
    (401/403/404/429 说明网关在线, 只是鉴权/资源/限流问题);
    5xx / 连接失败 / 超时 视为不健康。
    """

    def __init__(self, user_agent: str = DEFAULT_USER_AGENT) -> None:
        self.user_agent = user_agent

    def probe(self, base_url: str, timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
        t0 = time.monotonic()
        req = urllib.request.Request(
            base_url,
            headers={"User-Agent": self.user_agent, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.getcode()
                ok = status < 500
                error = None
        except urllib.error.HTTPError as e:
            status = e.code
            ok = status < 500
            error = None
            e.close()
        except Exception as e:  # URLError / TimeoutError / socket 层错误
            status = None
            ok = False
            error = "{0}: {1}".format(type(e).__name__, e)
        latency_ms = (time.monotonic() - t0) * 1000.0
        return {"ok": ok, "status": status, "latency_ms": latency_ms,
                "error": error}


# ================================================================ RelayManager

class RelayManager:
    """多端点(中转站)管理器: 注册 / 切换 / 健康检查 / 配置持久化。"""

    def __init__(self, transport: Optional[BaseTransport] = None,
                 config_path: Optional[str] = None) -> None:
        self._relays: Dict[str, Dict[str, Any]] = {}
        self._transport: BaseTransport = transport or UrllibTransport()
        self._rr_index = 0
        self.config_path = config_path
        if config_path and os.path.exists(config_path):
            self.load_config(config_path)

    # ------------------------------------------------------------ 端点注册

    def add_relay(self, name: str, base_url: str,
                  api_key_env: Optional[str] = None,
                  model: Optional[str] = None,
                  weight: float = 1.0) -> Dict[str, Any]:
        """注册一个端点。weight 权重参与切换(0 = 禁用)。"""
        if not name or not isinstance(name, str):
            raise RelayError("name 必须是非空字符串")
        if name in self._relays:
            raise RelayError("端点已存在: {0}".format(name))
        if (not isinstance(base_url, str) or
                not (base_url.startswith("http://") or
                     base_url.startswith("https://"))):
            raise RelayError("base_url 必须以 http:// 或 https:// 开头")
        parsed = urllib.parse.urlparse(base_url)
        if not parsed.netloc:
            raise RelayError("base_url 缺少主机名: {0}".format(base_url))
        if not isinstance(weight, (int, float)) or weight < 0:
            raise RelayError("weight 必须是 >= 0 的数字")
        if api_key_env is not None and not isinstance(api_key_env, str):
            raise RelayError("api_key_env 必须是字符串(环境变量名)")
        self._relays[name] = {
            "name": name,
            "base_url": base_url.rstrip("/"),
            "api_key_env": api_key_env,
            "model": model,
            "weight": float(weight),
            "health": None,        # None=未检查 / True=健康 / False=不健康
            "status": None,        # 最近一次探活的 HTTP 状态码
            "latency_ms": None,    # 最近一次探活延迟
            "last_check": None,    # 最近一次探活时间戳
            "error": None,         # 最近一次探活错误信息
        }
        return dict(self._relays[name])

    def remove_relay(self, name: str) -> Dict[str, Any]:
        """删除端点。"""
        if name not in self._relays:
            raise RelayError("未知端点: {0}".format(name))
        return dict(self._relays.pop(name))

    def get(self, name: str) -> Dict[str, Any]:
        if name not in self._relays:
            raise RelayError("未知端点: {0}".format(name))
        return dict(self._relays[name])

    def list_relays(self) -> List[Dict[str, Any]]:
        """端点列表(副本, 按注册顺序)。"""
        return [dict(r) for r in self._relays.values()]

    def stats(self) -> Dict[str, Any]:
        """端点统计: 总数 / 健康 / 不健康 / 未检查 / 平均延迟。"""
        total = len(self._relays)
        healthy = sum(1 for r in self._relays.values() if r["health"] is True)
        unhealthy = sum(1 for r in self._relays.values() if r["health"] is False)
        unchecked = total - healthy - unhealthy
        lat = [r["latency_ms"] for r in self._relays.values()
               if r["latency_ms"] is not None]
        return {
            "total": total,
            "healthy": healthy,
            "unhealthy": unhealthy,
            "unchecked": unchecked,
            "avg_latency_ms": (sum(lat) / len(lat)) if lat else None,
            "config_path": self.config_path,
        }

    def resolve_key(self, name: str) -> Optional[str]:
        """解析端点的 API key(从环境变量取, 不落盘明文)。"""
        env = self.get(name)["api_key_env"]
        if not env:
            return None
        return os.environ.get(env)

    # ------------------------------------------------------------ 健康检查

    def check(self, name: Optional[str] = None,
              transport: Optional[BaseTransport] = None,
              timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Dict[str, Any]]:
        """对全部(或指定)端点探活, 更新各端点健康状态。

        返回 {name: probe_result}。transport 可注入(测试时传 FakeTransport)。
        """
        targets = [name] if name is not None else list(self._relays.keys())
        unknown = [n for n in targets if n not in self._relays]
        if unknown:
            raise RelayError("未知端点: {0}".format(unknown))
        t = transport or self._transport
        out: Dict[str, Dict[str, Any]] = {}
        now = time.time()
        for n in targets:
            r = self._relays[n]
            res = t.probe(r["base_url"], timeout=timeout)
            r["health"] = bool(res["ok"])
            r["status"] = res.get("status")
            r["latency_ms"] = res.get("latency_ms")
            r["error"] = res.get("error")
            r["last_check"] = now
            out[n] = dict(res)
        return out

    # ------------------------------------------------------------ 端点切换

    def select(self, strategy: str = "health",
               check_first: bool = False,
               transport: Optional[BaseTransport] = None,
               timeout: float = DEFAULT_TIMEOUT) -> Optional[Dict[str, Any]]:
        """按策略选中一个端点, 返回端点 dict; 无可用端点返回 None。

        strategy:
          health      优先健康(排除上次探活不健康的), 在候选内按权重加权随机
          weight      纯按权重加权随机(忽略健康状态)
          round_robin 在启用(weight>0)的端点间轮询
          first       返回第一个健康状态不为 False 的端点(注册顺序)
        check_first=True 时先探活一轮再选。
        """
        relays = list(self._relays.values())
        if not relays:
            return None
        if check_first:
            self.check(transport=transport, timeout=timeout)

        if strategy == "round_robin":
            alive = [r for r in relays if r["weight"] > 0]
            if not alive:
                return None
            pick = alive[self._rr_index % len(alive)]
            self._rr_index += 1
            return dict(pick)

        if strategy == "first":
            for r in relays:
                if r["weight"] > 0 and r["health"] is not False:
                    return dict(r)
            return None

        if strategy == "health":
            candidates = [r for r in relays
                          if r["weight"] > 0 and r["health"] is not False]
        elif strategy == "weight":
            candidates = [r for r in relays if r["weight"] > 0]
        else:
            raise RelayError("未知策略: {0} (可选 health/weight/round_robin/first)"
                             .format(strategy))
        if not candidates:
            return None
        weights = [r["weight"] for r in candidates]
        return dict(random.choices(candidates, weights=weights, k=1)[0])

    # ------------------------------------------------------------ 配置持久化

    def save_config(self, path: Optional[str] = None) -> str:
        """保存配置为 JSON(只存端点定义, 不存运行时健康状态 / 明文 key)。"""
        path = path or self.config_path
        if not path:
            raise RelayError("未指定配置文件路径")
        data = {
            "version": CONFIG_VERSION,
            "relays": [
                {"name": r["name"], "base_url": r["base_url"],
                 "api_key_env": r["api_key_env"], "model": r["model"],
                 "weight": r["weight"]}
                for r in self._relays.values()
            ],
        }
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)   # 原子替换, 避免半截文件
        self.config_path = path
        return path

    def load_config(self, path: str) -> int:
        """从 JSON 加载配置(追加合并到现有端点), 返回加载的端点数。"""
        if not os.path.exists(path):
            raise RelayError("配置文件不存在: {0}".format(path))
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("version") != CONFIG_VERSION:
            raise RelayError("配置版本不兼容: {0} != {1}"
                             .format(data.get("version"), CONFIG_VERSION))
        relays = data.get("relays")
        if not isinstance(relays, list):
            raise RelayError("配置 relays 字段必须是数组")
        for item in relays:
            if not isinstance(item, dict) or not item.get("name"):
                raise RelayError("配置中存在无效的端点条目")
            self.add_relay(item["name"], item["base_url"],
                           api_key_env=item.get("api_key_env"),
                           model=item.get("model"),
                           weight=item.get("weight", 1.0))
        self.config_path = path
        return len(relays)

    @classmethod
    def from_config(cls, path: str,
                    transport: Optional[BaseTransport] = None) -> "RelayManager":
        """从配置文件构建管理器。"""
        m = cls(transport=transport)
        m.load_config(path)
        return m


# ================================================================ CLI

def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    p = argparse.ArgumentParser(
        prog="relay-manager",
        description="中转站管理: 多端点注册 / 切换 / 健康检查(纯标准库)")
    p.add_argument("--config", default=None,
                   help="配置文件路径(默认 ~/.relay-manager/config.json,"
                        " 可用环境变量 RELAY_CONFIG 覆盖)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("add", help="注册端点")
    pa.add_argument("--name", required=True, help="端点名(唯一)")
    pa.add_argument("--base-url", required=True, help="端点地址 http(s)://...")
    pa.add_argument("--api-key-env", default=None, help="API key 环境变量名")
    pa.add_argument("--model", default=None, help="默认模型名")
    pa.add_argument("--weight", type=float, default=1.0, help="权重(0=禁用)")

    pl = sub.add_parser("list", help="列出端点及健康状态")
    pl.add_argument("--stats", action="store_true", help="同时输出统计")

    pc = sub.add_parser("check", help="健康检查(探活)")
    pc.add_argument("--name", default=None, help="只检查指定端点")
    pc.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                    help="单端点超时秒数")

    ps = sub.add_parser("switch", help="切换端点(选中一个)")
    ps.add_argument("--strategy", default="health",
                    choices=["health", "weight", "round_robin", "first"])
    ps.add_argument("--check-first", action="store_true",
                    help="先探活一轮再切换")
    ps.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)

    args = p.parse_args(argv)
    config = (args.config or os.environ.get("RELAY_CONFIG")
              or os.path.expanduser("~/.relay-manager/config.json"))
    m = RelayManager(config_path=config)

    if args.cmd == "add":
        r = m.add_relay(args.name, args.base_url,
                        api_key_env=args.api_key_env, model=args.model,
                        weight=args.weight)
        m.save_config()
        print("已注册端点: {name} -> {base_url} (权重 {weight})".format(**r))
        print("配置已保存: {0}".format(m.config_path))

    elif args.cmd == "list":
        relays = m.list_relays()
        if not relays:
            print("(暂无端点, 用 relay-manager add --name ... --base-url ... 注册)")
        for r in relays:
            h = {True: "健康", False: "故障", None: "未检查"}[r["health"]]
            line = "{name:<20} {base_url:<48} 权重={weight:<5} {h}".format(h=h, **r)
            if r["latency_ms"] is not None:
                line += "  {0:.1f}ms".format(r["latency_ms"])
            if r["error"]:
                line += "  err={0}".format(r["error"])
            print(line)
        if args.stats:
            s = m.stats()
            print("--- 统计: 共 {total} | 健康 {healthy} | 故障 {unhealthy} | "
                  "未检查 {unchecked} | 平均延迟 {avg}".format(
                      avg=("None" if s["avg_latency_ms"] is None
                           else "{0:.1f}ms".format(s["avg_latency_ms"])), **s))

    elif args.cmd == "check":
        results = m.check(name=args.name, timeout=args.timeout)
        for n, res in results.items():
            mark = "OK" if res["ok"] else "FAIL"
            line = "[{0}] {1:<20} status={2} latency={3:.1f}ms".format(
                mark, n, res["status"], res["latency_ms"])
            if res["error"]:
                line += " error={0}".format(res["error"])
            print(line)

    elif args.cmd == "switch":
        pick = m.select(strategy=args.strategy, check_first=args.check_first,
                        timeout=args.timeout)
        if pick is None:
            print("无可用端点(全部故障或未注册)")
            return 1
        h = {True: "健康", False: "故障", None: "未检查"}[pick["health"]]
        print("已切换 -> {name} ({base_url}) 模型={model} 权重={weight} "
              "状态={h} 延迟={lat}".format(
                  h=h, lat=("None" if pick["latency_ms"] is None
                            else "{0:.1f}ms".format(pick["latency_ms"])), **pick))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
