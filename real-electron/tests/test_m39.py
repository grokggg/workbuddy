#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M39 测试: LLM 降级推理 + 网络协议模拟。"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # real-electron/
sys.path.insert(0, str(HERE))

from llm_fallback_engine import analyze  # noqa: E402
from grantmint_sim import (  # noqa: E402
    HAVE_CRYPTO,
    FailureReason,
    make_token,
    verify_token,
)


class TestLLMFallback(unittest.TestCase):
    def test_solve_license(self):
        """对 M38 auth-license 求解密码。"""
        p = HERE.parent / "real-auth" / "auth-license"
        if not os.path.exists(p):
            p = Path("/tmp/m39/restore/repo/real-auth/auth-license")
        if not os.path.exists(p):
            self.skipTest("auth-license 不存在")
        r = analyze(str(p))
        self.assertTrue(r.get("solved"))
        self.assertEqual(r["password"], "C")
        # 实测验证
        out = subprocess.run([str(p), "C"], capture_output=True, timeout=10)
        self.assertIn(b"OK", out.stdout)


class TestNetworkSim(unittest.TestCase):
    @unittest.skipUnless(HAVE_CRYPTO, "需要 cryptography")
    def test_verify_chain(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        import time
        priv = Ed25519PrivateKey.generate()
        pub = priv.public_key()
        now = int(time.time())
        # 正常
        tok = make_token(priv, "k1", "prod-A", now - 100, now + 3600)
        rc, _ = verify_token(tok, pub, "prod-A", now)
        self.assertEqual(rc, FailureReason.OK)
        # 篡改
        h, p, s = tok.split(".")
        import json, base64
        claims = json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))
        claims["prd"] = "prod-B"
        newp = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
        rc, _ = verify_token(f"{h}.{newp}.{s}", pub, "prod-A", now)
        self.assertEqual(rc, FailureReason.FORGED)
        # 过期
        tok2 = make_token(priv, "k1", "prod-A", now - 200, now - 100)
        rc, _ = verify_token(tok2, pub, "prod-A", now)
        self.assertEqual(rc, FailureReason.EXPIRED)
        # 伪造
        priv2 = Ed25519PrivateKey.generate()
        tok3 = make_token(priv2, "k1", "prod-A", now - 100, now + 3600)
        rc, _ = verify_token(tok3, pub, "prod-A", now)
        self.assertEqual(rc, FailureReason.FORGED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
