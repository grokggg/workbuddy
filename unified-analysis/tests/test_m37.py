#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M37 测试: 真实 asar 兼容 + 压测脚本。"""
from __future__ import annotations

import json
import os
import struct
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # unified-analysis/
sys.path.insert(0, str(HERE))

from process_asar import asar_extract, asar_pack  # noqa: E402


def make_real_asar(path: str) -> None:
    """构造真实格式 asar(offset 是字符串)。"""
    files = {"main.js": b"console.log('hi');"}
    header = {"files": {"main.js": {"size": len(files["main.js"]),
                                    "offset": "0"}}}
    hj = json.dumps(header, separators=(",", ":")).encode()
    pad = (4 - len(hj) % 4) % 4
    hj += b"\x00" * pad
    # 真实 asar: header_size 含 16 字节头 + json + padding
    header_size = 16 + len(hj)
    with open(path, "wb") as f:
        f.write(struct.pack("<I", 4))
        f.write(struct.pack("<I", header_size))
        f.write(struct.pack("<I", len(hj)))
        f.write(struct.pack("<I", len(files["main.js"])))
        f.write(hj)
        f.write(files["main.js"])


class TestM37(unittest.TestCase):
    def test_real_asar_string_offset(self):
        """真实 asar(offset 字符串)应能解包(M37 修复)。"""
        import tempfile
        tmp = tempfile.mkdtemp(prefix="m37-")
        p = os.path.join(tmp, "real.asar")
        make_real_asar(p)
        out = os.path.join(tmp, "out")
        info = asar_extract(p, out)
        self.assertEqual(len(info["files"]), 1)
        content = open(os.path.join(out, "main.js")).read()
        self.assertIn("console.log", content)

    def test_real_asar_roundtrip(self):
        """解包→重打包→再解包。"""
        import tempfile
        tmp = tempfile.mkdtemp(prefix="m37-")
        p = os.path.join(tmp, "real.asar")
        make_real_asar(p)
        out = os.path.join(tmp, "out")
        info = asar_extract(p, out)
        rep = os.path.join(tmp, "rep.asar")
        asar_pack(out, rep)
        out2 = os.path.join(tmp, "out2")
        info2 = asar_extract(rep, out2)
        c1 = open(os.path.join(out, "main.js")).read()
        c2 = open(os.path.join(out2, "main.js")).read()
        self.assertEqual(c1, c2)

    def test_stress_script_exists(self):
        sp = HERE.parent / "orchestrator" / "stress_test.py"
        self.assertTrue(sp.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
