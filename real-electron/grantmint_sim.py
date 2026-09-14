#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
grantmint_sim.py —— M39 真实网络验证协议模拟闭环

复刻 grantmint LicenseVerifier 的 7 步验证链(pure Python 教学模拟):
  客户端: 构造 Ed25519 签名 token
  服务端: 7 步验证 → VerificationResult / FailureReason

不对任何真实服务发起请求; 仅演示协议机制。
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time

# 用纯 Python ed25519 实现(pip install ed25519 或 cryptography)
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives import serialization
    HAVE_CRYPTO = True
except ImportError:
    HAVE_CRYPTO = False


class FailureReason:
    MALFORMED = "MALFORMED"
    ALG_NOT_ALLOWED = "ALG_NOT_ALLOWED"
    WRONG_TYPE = "WRONG_TYPE"
    FORGED = "FORGED"
    UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"
    WRONG_PRODUCT = "WRONG_PRODUCT"
    NOT_YET_VALID = "NOT_YET_VALID"
    EXPIRED = "EXPIRED"
    OK = "OK"


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64u(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def make_token(priv: object, kid: str, prd: str, nbf: int, exp: int, ver: int = 1) -> str:
    """客户端: 构造 Ed25519 签名 token(三段式)。"""
    header = {"alg": "EdDSA", "typ": "license", "kid": kid}
    payload = {"ver": ver, "prd": prd, "nbf": nbf, "exp": exp}
    h = b64u(json.dumps(header, separators=(",", ":")).encode())
    p = b64u(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{h}.{p}".encode()
    sig = priv.sign(signing_input)
    return f"{h}.{p}.{b64u(sig)}"


def verify_token(token: str, pub: object, expected_product: str | None,
                 clock: int, keys: dict | None = None) -> tuple[str, str]:
    """服务端: 7 步验证链(复刻 grantmint LicenseVerifier)。"""
    keys = keys or {"k1": pub}
    # 1. 结构解析
    try:
        h, p, s = token.split(".")
        hdr = json.loads(unb64u(h))
        payload_b = unb64u(p)
        sig = unb64u(s)
    except Exception:
        return FailureReason.MALFORMED, "段结构/base64 解码失败"
    # 2. 签名方案 pinning
    if hdr.get("alg") != "EdDSA":
        return FailureReason.ALG_NOT_ALLOWED, f"alg={hdr.get('alg')}"
    # 2b. 类型 pinning
    if hdr.get("typ") != "license":
        return FailureReason.WRONG_TYPE, f"typ={hdr.get('typ')}"
    # 3. Ed25519 签名验证(收到的字节)
    key = keys.get(hdr.get("kid", ""))
    if key is None:
        return FailureReason.FORGED, f"未知 kid={hdr.get('kid')}"
    try:
        key.verify(sig, f"{h}.{p}".encode())
    except Exception:
        return FailureReason.FORGED, "Ed25519 签名不匹配"
    # 4. claims 解析
    try:
        claims = json.loads(payload_b)
    except Exception:
        return FailureReason.MALFORMED, "payload JSON 解析失败"
    # 5. 格式版本门
    if claims.get("ver") != 1:
        return FailureReason.UNSUPPORTED_VERSION, f"ver={claims.get('ver')}"
    # 6. 产品绑定
    if expected_product is not None and claims.get("prd") != expected_product:
        return FailureReason.WRONG_PRODUCT, f"prd={claims.get('prd')}"
    # 7. 时间有效性
    if claims.get("nbf") is not None and clock < claims["nbf"]:
        return FailureReason.NOT_YET_VALID, f"now={clock} nbf={claims['nbf']}"
    if claims.get("exp") is not None and clock >= claims["exp"]:
        return FailureReason.EXPIRED, f"now={clock} exp={claims['exp']}"
    return FailureReason.OK, "验证通过"


def main():
    if not HAVE_CRYPTO:
        print("[!] 需要 cryptography: pip install cryptography")
        sys.exit(1)
    now = int(time.time())
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()

    print("=== grantmint 协议模拟闭环(7 步验证链) ===")
    # 正常 token
    tok = make_token(priv, "k1", "prod-A", now - 100, now + 3600)
    rc, msg = verify_token(tok, pub, "prod-A", now)
    print(f"  正常 token   -> {rc} ({msg})")

    # 篡改 payload(签名失效)
    h, p, s = tok.split(".")
    claims = json.loads(unb64u(p)); claims["prd"] = "prod-B"
    forged = f"{h}.{b64u(json.dumps(claims).encode())}.{s}"
    rc, msg = verify_token(forged, pub, "prod-A", now)
    print(f"  篡改 payload -> {rc} ({msg})")

    # 过期 token
    tok2 = make_token(priv, "k1", "prod-A", now - 200, now - 100)
    rc, msg = verify_token(tok2, pub, "prod-A", now)
    print(f"  过期 token   -> {rc} ({msg})")

    # 未生效 token(nbf 在未来)
    tok3 = make_token(priv, "k1", "prod-A", now + 500, now + 3600)
    rc, msg = verify_token(tok3, pub, "prod-A", now)
    print(f"  未生效 token -> {rc} ({msg})")

    # 错误产品
    tok4 = make_token(priv, "k1", "prod-B", now - 100, now + 3600)
    rc, msg = verify_token(tok4, pub, "prod-A", now)
    print(f"  错产品 token -> {rc} ({msg})")

    # 错误签名(伪造)
    priv2 = Ed25519PrivateKey.generate()
    tok5 = make_token(priv2, "k1", "prod-A", now - 100, now + 3600)
    rc, msg = verify_token(tok5, pub, "prod-A", now)
    print(f"  伪造签名     -> {rc} ({msg})")

    print()
    print("=== 结论 ===")
    print("Ed25519 签名验证无法数学绕过; 所有篡改/伪造/过期/错产品都被拒绝。")


if __name__ == "__main__":
    main()
