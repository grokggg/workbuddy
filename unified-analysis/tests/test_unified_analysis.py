#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M31 测试: 统一入口 + asar 处理。"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # unified-analysis/
sys.path.insert(0, str(HERE))

from process_asar import asar_extract, asar_pack  # noqa: E402


def make_mini_asar(path: str) -> None:
    """构造最小 asar(M23 格式)。"""
    import struct
    files = {"main.js": b"function checkLicense(k) {\n  return hash === 'x';\n}\n"}
    header = {"files": {"main.js": {"size": len(files["main.js"])}}}
    hj = json.dumps(header, separators=(",", ":")).encode()
    pad = (4 - len(hj) % 4) % 4
    hj += b"\x00" * pad
    with open(path, "wb") as f:
        f.write(struct.pack("<I", 4))
        f.write(struct.pack("<I", len(hj)))
        f.write(struct.pack("<I", len(hj)))
        f.write(struct.pack("<I", len(files["main.js"])))
        f.write(hj)
        f.write(files["main.js"])


class TestUnifiedAnalysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="m31-")
        cls.asar = os.path.join(cls.tmp, "app.asar")
        make_mini_asar(cls.asar)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_asar_roundtrip(self):
        """解包 -> 重打包 -> 再解包, 内容一致。"""
        ex = os.path.join(self.tmp, "ex")
        info = asar_extract(self.asar, ex)
        self.assertEqual(len(info["files"]), 1)
        self.assertEqual(info["files"][0]["path"], "main.js")
        content = open(os.path.join(ex, "main.js")).read()
        self.assertIn("checkLicense", content)
        # 重打包
        out = os.path.join(self.tmp, "out.asar")
        asar_pack(ex, out)
        # 再解包
        ex2 = os.path.join(self.tmp, "ex2")
        info2 = asar_extract(out, ex2)
        self.assertEqual(len(info2["files"]), 1)
        content2 = open(os.path.join(ex2, "main.js")).read()
        self.assertEqual(content, content2)

    def test_asar_patch(self):
        """修改 main.js 后重打包, 验证生效。"""
        ex = os.path.join(self.tmp, "ex-p")
        asar_extract(self.asar, ex)
        p = os.path.join(ex, "main.js")
        src = open(p).read()
        open(p, "w").write(src.replace("return hash === 'x'",
                                       "return true;  // PATCH"))
        out = os.path.join(self.tmp, "patched.asar")
        asar_pack(ex, out)
        ex2 = os.path.join(self.tmp, "ex-p2")
        asar_extract(out, ex2)
        c = open(os.path.join(ex2, "main.js")).read()
        self.assertIn("return true", c)

    def test_analysis_all_module(self):
        """统一入口模块可导入。"""
        import analysis_all
        self.assertTrue(hasattr(analysis_all, "UnifiedAnalyzer"))

    def test_analysis_all_on_cm(self):
        """统一入口处理 crackme 应生成破解版。"""
        import analysis_all
        cm = Path(HERE).parent / "real-crackmes" / "cm01"
        if not cm.exists():
            self.skipTest("cm01 不存在")
        a = analysis_all.UnifiedAnalyzer(str(cm), self.tmp)
        rep = a.run()
        cracked = rep.get("cracked_path", "")
        self.assertTrue(os.path.exists(cracked))
        # argv 验证
        r = subprocess.run([cracked, "x"], capture_output=True, timeout=10)
        self.assertEqual(r.returncode, 0)
        self.assertIn("OK", r.stdout.decode(errors="ignore"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
