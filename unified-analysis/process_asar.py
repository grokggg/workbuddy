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
    jsize = struct.unpack("<I", d[8:12])[0]
    # 数据起点按头字段关系判别(三种历史格式):
    #   Node/真实 asar: [4:8]=[8:12]+4 → 数据区 = 8 + [4:8]
    #   旧测试 fixture: [4:8]=[8:12]+16 → 数据区 = 16 + [8:12]
    #   M23 自建:       [4:8]==[8:12]  → 数据区 = 16 + [4:8]
    hsize = struct.unpack("<I", d[4:8])[0]
    jsize = struct.unpack("<I", d[8:12])[0]
    diff = hsize - jsize
    if diff == 4:
        data_start = 8 + hsize
    elif diff == 16:
        data_start = 16 + jsize
    else:
        data_start = 16 + hsize
    files = []

    def walk(node, prefix):
        for name, info in node.get("files", {}).items():
            rel = f"{prefix}/{name}" if prefix else name
            if "files" in info:
                walk(info, rel)
            else:
                # 真实 asar 的 offset 是十进制字符串, 转 int
                off_str = info.get("offset", 0)
                rel_off = int(off_str) if not isinstance(off_str, int) else off_str
                off = data_start + rel_off
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
    out_abs = os.path.abspath(out_path)
    files = {}
    for root, dirs, fnames in os.walk(src_dir):
        for fn in sorted(fnames):
            p = os.path.join(root, fn)
            if os.path.abspath(p) == out_abs:
                continue  # 排除输出文件自身(避免把 app.asar 打进去)
            rel = os.path.relpath(p, src_dir).replace(os.sep, "/")
            files[rel] = os.path.getsize(p)
    header = {"files": {}}
    ordered = sorted(files.items())
    data_off = 0
    for rel, size in ordered:
        parts = rel.split("/")
        cur = header["files"]
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                cur[part] = {"size": size, "offset": str(data_off)}
            else:
                cur = cur.setdefault(part, {"files": {}})["files"]
        data_off += size
    header_json = json.dumps(header, separators=(",", ":")).encode()
    # padding 统一在写入时处理(align 8, 见下), 此处不提前 pad
    with open(out_path, "wb") as f:
        f.write(struct.pack("<I", 4))
        jlen = len(header_json)
        align4 = (jlen + 3) & ~3  # Pickle.writeBytes 按 4 对齐
        f.write(struct.pack("<I", 8 + align4))  # sizePickle payload = headerBuf.length
        f.write(struct.pack("<I", 4 + align4))  # headerPickle payloadSize
        f.write(struct.pack("<I", jlen))        # writeInt(JSON 长度)
        f.write(header_json)
        f.write(b"\x00" * (align4 - jlen))      # pad 到 4 对齐
        # 数据区(Node 公式) = 8 + [4:8] + fileOffset = 8 + 8 + align4 = 16 + align4
        # 与写入位置 16 + align4 完全一致
        data_size = 0
        for rel, size in ordered:
            with open(os.path.join(src_dir, rel), "rb") as sf:
                f.write(sf.read())
            data_size += size
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
