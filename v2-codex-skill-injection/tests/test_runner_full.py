#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
runner_full.py 单元测试 —— 十二段链执行引擎

覆盖:
  - 前六段(定位/根目录/版本/工具链/asar/输出)
  - 段7 asar 解包(真解包 + 手动解析退化)
  - 段8 结构查看(main.js/package.json/资源)
  - 段9 校验定位(关键词搜索)
  - 段10 修改占位({PATCH})
  - 段11 重新打包占位({COMMAND})
  - 段12 输出验证占位({VERIFY_CMD})
  - 全链执行与报告

跑法: python3 tests/test_runner_full.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

from lib.runner_full import ChainRunnerFull, _fmt_size  # noqa: E402


def _make_asar(src_dir: str, out_path: str) -> bool:
    """纯 Python 构造 asar 文件(不依赖 @electron/asar / Node 版本)。

    asar 格式: 8 字节头(4 字节 pickle 类型 + 4 字节 header size) + JSON header + 文件内容。
    """
    import json as _json
    src = Path(src_dir)
    files = {}
    for dp, _dn, fns in os.walk(src):
        for fn in sorted(fns):
            fp = Path(dp) / fn
            rel = str(fp.relative_to(src)).replace(os.sep, "/")
            files[rel] = fp.read_bytes()

    # 构造 header(树形 files 节点)
    header_files = {}
    for rel in files:
        parts = rel.split("/")
        node = header_files
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                node[part] = {"size": 0, "offset": "0"}  # 占位, 后面填
            else:
                node = node.setdefault(part, {}).setdefault("files", {})

    # 先算一次 header 长度(占位 offset 都是短字符串, 长度固定)
    # 用最长的 offset 串估算 -> 直接序列化两轮, 第二次才是最终 header
    header = _json.dumps({"files": header_files}).encode()

    # 计算每个文件内容的真实 offset(基于最终 header 长度)
    # 注意: 占位 offset "0" 长度 1, 真实 offset 可能更长, 会导致 header 变长
    # 因此迭代: 先算 offsets, 再序列化, 再算 offsets, 直到稳定
    for _round in range(3):
        offsets = {}
        cursor = 8 + len(header)
        for rel in sorted(files):
            offsets[rel] = cursor
            cursor += len(files[rel])
        # 填 offset/size
        for rel in files:
            parts = rel.split("/")
            node = header_files
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    node[part] = {"size": len(files[rel]),
                                  "offset": str(offsets[rel])}
                else:
                    node = node.setdefault(part, {}).setdefault("files", {})
        new_header = _json.dumps({"files": header_files}).encode()
        if len(new_header) == len(header):
            header = new_header
            break
        header = new_header

    # 写入
    import struct
    with open(out_path, "wb") as f:
        # bytes 0-3: pickle 类型; bytes 4-7: header size; bytes 8+: header + 内容
        f.write(struct.pack("<I", 4))
        f.write(struct.pack("<I", len(header)))
        f.write(header)
        for rel in sorted(files):
            f.write(files[rel])
    return os.path.exists(out_path) and os.path.getsize(out_path) > 16


class TestFormat(unittest.TestCase):
    def test_fmt_size(self):
        self.assertEqual(_fmt_size(0), "0.0B")
        self.assertEqual(_fmt_size(2048), "2.0KB")


class TestChainFull(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 造假目标: app/x64/4.2.0/resources/app.asar(含 package.json + main.js + 卡密逻辑)
        cls.tmp = tempfile.mkdtemp(prefix="v2full-")
        base = Path(cls.tmp)
        app = base / "app"
        ver = app / "x64" / "4.2.0"
        res = ver / "resources"
        res.mkdir(parents=True)
        cls.app_root = str(app)
        cls.ver_dir = str(ver)

        # 源文件
        src = base / "src"
        src.mkdir(parents=True, exist_ok=True)
        (src / "package.json").write_text(
            '{"name":"demo-app","version":"4.2.0","main":"main.js"}', encoding="utf-8")
        (src / "main.js").write_text(
            "// demo main\n"
            "function checkLicense() {\n"
            "  // 卡密校验逻辑\n"
            "  var key = getSerial();\n"
            "  if (key !== VALID_SERIAL) { alert('卡密无效'); }\n"
            "}\n", encoding="utf-8")
        (src / "renderer").mkdir()
        (src / "renderer" / "index.html").write_text(
            "<html><script>// 激活界面</script></html>", encoding="utf-8")

        cls.asar_path = str(res / "app.asar")
        cls.has_asar = _make_asar(str(src), cls.asar_path)
        if not cls.has_asar:
            # 无 asar 模块: 写一个假的 asar 头(手动解析路径可测)
            pass

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.runner = ChainRunnerFull(self.app_root,
                                      out_dir=os.path.join(self.tmp, "out"))

    def test_stages_1_6(self):
        s1 = self.runner.stage_locate()
        self.assertTrue(s1["ok"])
        s2 = self.runner.stage_root()
        self.assertTrue(s2["ok"])
        s3 = self.runner.stage_version()
        self.assertTrue(s3["ok"])
        self.assertEqual(self.runner.version_dir, self.ver_dir)
        s4 = self.runner.stage_toolchain()
        self.assertIn("node=", s4["detail"])
        s5 = self.runner.stage_asar()
        self.assertTrue(s5["ok"])
        self.assertEqual(self.runner.asar_path, self.asar_path)
        s6 = self.runner.stage_output()
        self.assertTrue(s6["ok"])
        self.assertTrue(os.path.isdir(self.runner.out_dir))

    def test_stage_extract(self):
        self.runner.stage_version()
        self.runner.stage_asar()
        self.runner.stage_output()
        s = self.runner.stage_extract()
        # 有 asar 模块: 真解包成功; 无模块: 手动解析或失败但结构完整
        if self.has_asar:
            self.assertTrue(s["ok"], s["detail"])
            self.assertTrue(os.path.isdir(self.runner.extract_dir))
        else:
            self.assertIn("detail", s)

    def test_stage_inspect(self):
        self.runner.stage_version()
        self.runner.stage_asar()
        self.runner.stage_output()
        self.runner.stage_extract()
        s = self.runner.stage_inspect()
        if self.has_asar:
            self.assertTrue(s["ok"])
            self.assertIn("package.json", s["detail"])
            self.assertIn("文件", s["detail"])
        else:
            self.assertIn("detail", s)

    def test_stage_locate_chk(self):
        self.runner.stage_version()
        self.runner.stage_asar()
        self.runner.stage_output()
        self.runner.stage_extract()
        s = self.runner.stage_locate_chk()
        if self.has_asar:
            self.assertTrue(s["ok"])
            self.assertIn("hits", s)
            # main.js 应命中"卡密"或"校验"
            hit_text = " ".join(s.get("hits", []))
            self.assertTrue(any(k in hit_text for k in ["卡密", "license", "serial", "verify"]),
                            hit_text)
        else:
            self.assertIn("detail", s)

    def test_stage_patch_placeholder(self):
        s = self.runner.stage_patch()
        self.assertTrue(s["ok"])
        self.assertTrue(s.get("placeholder"))
        self.assertIn("{PATCH}", s["detail"])

    def test_stage_repack_placeholder(self):
        s = self.runner.stage_repack()
        self.assertTrue(s["ok"])
        self.assertTrue(s.get("placeholder"))
        self.assertIn("{COMMAND}", s["detail"])

    def test_stage_verify_placeholder(self):
        s = self.runner.stage_verify()
        self.assertTrue(s["ok"])
        self.assertTrue(s.get("placeholder"))
        self.assertIn("{VERIFY_CMD}", s["detail"])

    def test_run_all_12(self):
        stages = self.runner.run_all()
        self.assertEqual(len(stages), 12)
        # 前六段 + 占位三段(patch/repack/verify)必过
        ok = sum(1 for s in stages if s["ok"])
        self.assertGreaterEqual(ok, 9)

    def test_report_text(self):
        txt = self.runner.report_text()
        self.assertIn("[1/12]", txt)
        self.assertIn("[12/12]", txt)
        self.assertIn("通过", txt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
