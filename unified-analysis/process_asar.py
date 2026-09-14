#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_asar.py —— M31 Electron 应用(asar)处理

流程:
  1. asar 解包(纯 Python)
  2. 定位卡密/登录校验逻辑(main.js)
  3. 修改校验({PATCH} 具体位置)
  4. 重打包
  5. 验证

注意: 处理的是教学用 asar(M23 自建, 含卡密校验), 演示完整流程。
"""
import json
import os
import struct
import sys


def asar_extract(path: str, out_dir: str) -> dict:
    """纯 Python asar 解包。返回文件清单。"""
    d = open(path, "rb").read()
    # 头: [4B pickle][4B hsize][4B jsize][4B dsize][json][data]
    jsize = struct.unpack("<I", d[8:12])[0]
    raw = d[16:16 + jsize]
    # json 可能含 padding(实际结束于最后一个 })
    end = raw.rfind(b"}")
    header = json.loads(raw[:end + 1].decode())
    header_size = struct.unpack("<I", d[4:8])[0]
    data_start = 16 + header_size
    files = []

    def walk(node, prefix):
        for name, info in node.get("files", {}).items():
            rel = f"{prefix}/{name}" if prefix else name
            if "files" in info:
                walk(info, rel)
            else:
                off = data_start + info.get("offset", 0)
                size = info.get("size", 0)
                files.append({"path": rel, "offset": off, "size": size})

    walk(header, "")
    os.makedirs(out_dir, exist_ok=True)
    for f in files:
        p = os.path.join(out_dir, f["path"])
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(d[f["offset"]:f["offset"] + f["size"]])
    return {"header": header, "files": files, "data_start": data_start}


def asar_pack(src_dir: str, out_path: str) -> int:
    """纯 Python asar 打包。"""
    files = {}
    for root, dirs, fnames in os.walk(src_dir):
        for fn in sorted(fnames):
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, src_dir).replace(os.sep, "/")
            files[rel] = os.path.getsize(p)
    header = {"files": {}}
    for rel, size in sorted(files.items()):
        parts = rel.split("/")
        cur = header["files"]
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                cur[part] = {"size": size}
            else:
                cur = cur.setdefault(part, {"files": {}})["files"]
    header_json = json.dumps(header, separators=(",", ":")).encode()
    pad = (4 - len(header_json) % 4) % 4
    header_json += b"\x00" * pad
    with open(out_path, "wb") as f:
        f.write(struct.pack("<I", 4))
        f.write(struct.pack("<I", len(header_json)))
        f.write(struct.pack("<I", len(header_json)))
        f.write(struct.pack("<I", 0))  # data size placeholder
        f.write(header_json)
        data_size = 0
        for rel, size in sorted(files.items()):
            with open(os.path.join(src_dir, rel), "rb") as sf:
                f.write(sf.read())
            data_size += size
        f.seek(12)
        f.write(struct.pack("<I", data_size))
    return os.path.getsize(out_path)


def main():
    if len(sys.argv) < 2:
        print("用法: process_asar.py <app.asar> [工作目录]")
        return 1
    asar_path = sys.argv[1]
    work = sys.argv[2] if len(sys.argv) > 2 else "asar-work"
    os.makedirs(work, exist_ok=True)

    # 1. 解包
    extract_dir = os.path.join(work, "extracted")
    info = asar_extract(asar_path, extract_dir)
    print(f"=== asar 解包 ===")
    print(f"文件数: {len(info['files'])}")
    for f in info["files"]:
        print(f"  {f['path']} ({f['size']}B)")

    # 2. 定位校验逻辑
    print(f"\n=== 定位校验逻辑 ===")
    checks = []
    for f in info["files"]:
        p = os.path.join(extract_dir, f["path"])
        content = open(p, "rb").read()
        for kw in (b"license", b"checkLicense", b"verifyIntegrity",
                   b"activation", b"serial", b"checksum"):
            idx = content.find(kw)
            if idx != -1:
                checks.append({"file": f["path"], "keyword": kw.decode(),
                               "offset": idx})
    print(f"校验相关: {len(checks)} 处")
    for c in checks:
        print(f"  {c['file']} @ {c['offset']:#x}: {c['keyword']}")

    # 3. 修改(演示: 把校验函数返回固定 true)
    print(f"\n=== 修改校验逻辑 ===")
    main_js = os.path.join(extract_dir, "main.js")
    if os.path.exists(main_js):
        src = open(main_js).read()
        # 找 checkLicense 的返回: 把 return hash === ... 改成 return true
        modified = False
        if "checkLicense" in src:
            lines = src.split("\n")
            for i, line in enumerate(lines):
                if "return hash ===" in line:
                    lines[i] = "  return true;  // PATCH: 绕过卡密校验"
                    modified = True
            src = "\n".join(lines)
        if modified:
            open(main_js, "w").write(src)
            print(f"  main.js: checkLicense 改为 return true")
        else:
            print(f"  main.js: 未找到卡密返回(检查源码)")

    # 4. 重打包
    print(f"\n=== 重打包 ===")
    out_asar = os.path.join(work, "app-patched.asar")
    size = asar_pack(extract_dir, out_asar)
    print(f"  {out_asar} ({size}B)")

    # 5. 验证(解包 patched asar 确认修改)
    print(f"\n=== 验证 ===")
    verify_dir = os.path.join(work, "verify")
    info2 = asar_extract(out_asar, verify_dir)
    v_main = open(os.path.join(verify_dir, "main.js")).read()
    patched = "return true" in v_main
    print(f"  patched asar 解包: {len(info2['files'])} 文件")
    print(f"  main.js 含 return true: {patched}")
    print(f"  ✅ 修改验证通过" if patched else "  ❌ 修改未生效")

    # 保存报告
    report = {"asar": asar_path, "files": info["files"],
              "checks": checks, "patched": patched,
              "out": out_asar}
    with open(os.path.join(work, "report.json"), "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
