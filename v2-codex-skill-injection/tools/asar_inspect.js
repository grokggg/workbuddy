#!/usr/bin/env node
/**
 * asar_inspect.js —— Electron asar 结构查看与解包
 *
 * 复现 BV15y3U6oEmt 第 6 步的**工具链环节**：视频里模型调
 * `npx --yes @electron/asar` 去解包目标 app.asar。
 * 这一步本身是合法的 Electron 开发操作，所以保留；
 * 视频里"解完之后做什么"属于越权操作，不在本文件范围内。
 *
 * 范围（写死在代码里，不是注释里的建议）：
 *   - 只做 list / extract / info 三件事
 *   - 不做任何写回、打包、打补丁
 *   - 不接触授权校验、许可证相关的文件逻辑
 *
 * 用法：
 *   node asar_inspect.js list    <app.asar>
 *   node asar_inspect.js extract <app.asar> [输出目录]
 *   node asar_inspect.js info    <app.asar>
 */
'use strict';

const fs = require('fs');
const path = require('path');

// ---------------------------------------------------------------- 只做这三件事
const ACTIONS = ['list', 'extract', 'info'];

/**
 * 失败处理：抛异常，不直接 process.exit。
 * 库函数里调 exit 会把调用方（含单元测试）一起杀掉 —— 实测踩过：
 * 测试调 main() 断言"未知动作要报错"，结果 die() 先 exit(2)，整个测试进程没了。
 * 退出只在 require.main === module 的那一层做。
 */
function die(msg) {
  const e = new Error(msg);
  e.cliError = true;
  throw e;
}

function loadAsar() {
  // @electron/asar 是可选依赖：本地装了就用本地的，没有就提示用 npx。
  const candidates = [
    '@electron/asar',
    'asar',
  ];
  for (const name of candidates) {
    try {
      return require(name);
    } catch (e) {
      /* 继续找下一个 */
    }
  }
  return null;
}

function ensureFile(p) {
  if (!p) die('缺文件路径');
  if (!fs.existsSync(p)) die('文件不存在：' + p);
  const st = fs.statSync(p);
  if (!st.isFile()) die('不是文件：' + p);
  return p;
}

/**
 * 校验 asar 头：8 字节 magic + 4 字节 uint32 header size。
 * 不做这一步的话，传个任意文件进来会在很后面才报错，且报错信息莫名其妙。
 */
function readHeaderSize(file) {
  const fd = fs.openSync(file, 'r');
  try {
    const magic = Buffer.alloc(8);
    fs.readSync(fd, magic, 0, 8, 0);
    // asar 的 magic：4 字节 4 (uint32 LE) + 4 字节 header 字符串长度占位
    const sizeBuf = Buffer.alloc(8);
    fs.readSync(fd, sizeBuf, 0, 8, 8);
    // header pickle: [uint32 headerStringSize][uint32 headerSize]
    const headerSize = sizeBuf.readUInt32LE(0);
    const headerStrSize = sizeBuf.readUInt32LE(4);
    return { headerStrSize, headerSize };
  } finally {
    fs.closeSync(fd);
  }
}

function parseHeader(file) {
  const { headerStrSize } = readHeaderSize(file);
  const fd = fs.openSync(file, 'r');
  try {
    // 布局：8 字节 magic + 4 + 4 之后才是 header 字符串
    const buf = Buffer.alloc(headerStrSize);
    fs.readSync(fd, buf, 0, headerStrSize, 16);
    // 兼容 padding：部分实现（纯 Python asar_pack）会把 header JSON
    // padding 到 4 字节对齐，尾部带 \x00，Node 严格 JSON.parse 会报 Extra data。
    let s = buf.toString('utf8');
    s = s.replace(/\x00+$/, '');
    return JSON.parse(s);
  } finally {
    fs.closeSync(fd);
  }
}

// ---------------------------------------------------------------- 动作
function walk(node, prefix, out) {
  const files = node.files || {};
  for (const name of Object.keys(files)) {
    const child = files[name];
    const p = prefix ? prefix + '/' + name : '/' + name;
    if (child.files) {
      out.push({ path: p, type: 'dir' });
      walk(child, p, out);
    } else {
      out.push({
        path: p,
        type: 'file',
        size: child.size,
        unpacked: !!child.unpacked,
      });
    }
  }
}

function cmdList(file) {
  const header = parseHeader(file);
  const out = [];
  walk(header, '', out);
  const files = out.filter((e) => e.type === 'file');
  const dirs = out.filter((e) => e.type === 'dir');
  const total = files.reduce((a, b) => a + (b.size || 0), 0);
  process.stdout.write(`文件 ${files.length} 个 / 目录 ${dirs.length} 个`
    + ` / 合计 ${total} 字节\n`);
  for (const e of out) {
    if (e.type === 'dir') continue;
    process.stdout.write(`  ${String(e.size).padStart(8)}  ${e.path}`
      + `${e.unpacked ? '  [unpacked]' : ''}\n`);
  }
  return { files: files.length, dirs: dirs.length, bytes: total };
}

function cmdInfo(file) {
  const header = parseHeader(file);
  const out = [];
  walk(header, '', out);
  const files = out.filter((e) => e.type === 'file');
  const pkgEntry = files.find((e) => /(^|\/)package\.json$/.test(e.path));
  let pkg = null;
  let pkgError = null;
  const asar = loadAsar();
  if (pkgEntry && asar && typeof asar.extractFile === 'function') {
    // 坑：@electron/asar 的 extractFile 不接受前导斜杠。
    // walk() 产出的路径带 '/'，直接传会报 "was not found in this archive"。
    const rel = pkgEntry.path.replace(/^\/+/, '');
    try {
      const buf = asar.extractFile(file, rel);
      pkg = JSON.parse(buf.toString('utf8'));
    } catch (e) {
      // 不静默吞：读不出来要在输出里说明，否则看起来像"这个 asar 没有 package.json"
      pkgError = e.message;
    }
  }
  const info = {
    asar: path.resolve(file),
    bytes: fs.statSync(file).size,
    files: files.length,
    dirs: out.filter((e) => e.type === 'dir').length,
    totalBytes: files.reduce((a, b) => a + (b.size || 0), 0),
    // package 为 null 时，packageError 说明是"没有"还是"读失败"
    package: pkg
      ? { name: pkg.name, version: pkg.version, main: pkg.main }
      : null,
    packageError: pkgError,
    asarModule: asar ? 'available' : 'missing',
  };
  process.stdout.write(JSON.stringify(info, null, 2) + '\n');
  return info;
}

function cmdExtract(file, outDir) {
  const asar = loadAsar();
  if (!asar) {
    die('未找到 @electron/asar。安装：npm i @electron/asar'
      + ' 或用 npx --yes @electron/asar extract <asar> <dir>');
  }
  const stamp = new Date().toISOString().slice(0, 10);
  const dir = outDir
    || path.join(process.env.HOME || '.', 'Documents', 'Codex', stamp, 'work',
      path.basename(file, '.asar') + '-' + Date.now());
  fs.mkdirSync(dir, { recursive: true });
  asar.extractAll(file, dir);
  let n = 0;
  (function count(d) {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, e.name);
      if (e.isDirectory()) count(p);
      else n++;
    }
  })(dir);
  process.stdout.write(`已解包 ${n} 个文件 → ${dir}\n`);
  return { outDir: dir, files: n };
}

// ---------------------------------------------------------------- main
/**
 * 返回退出码，不自己 exit。出错抛 Error（cliError=true）。
 */
function main(argv) {
  const [action, file, outDir] = argv;
  if (!action || action === '--help' || action === '-h') {
    process.stdout.write(
      '用法：\n'
      + '  node asar_inspect.js list    <app.asar>\n'
      + '  node asar_inspect.js extract <app.asar> [输出目录]\n'
      + '  node asar_inspect.js info    <app.asar>\n'
      + '\n范围：只做结构查看与解包，不做写回/打包/打补丁。\n');
    return 0;
  }
  if (!ACTIONS.includes(action)) {
    die(`未知动作 ${action}，可选：${ACTIONS.join(' / ')}`);
  }
  const target = ensureFile(file);
  if (action === 'list') cmdList(target);
  else if (action === 'info') cmdInfo(target);
  else cmdExtract(target, outDir);
  return 0;
}

// CLI 层：把异常翻译成 stderr + 退出码。只有这一层碰 process.exit。
function runCli(argv) {
  try {
    return main(argv);
  } catch (e) {
    process.stderr.write('错误：' + e.message + '\n');
    return e.cliError ? 2 : 1;
  }
}

if (require.main === module) {
  process.exit(runCli(process.argv.slice(2)));
}

module.exports = { main, cmdList, cmdInfo, cmdExtract, parseHeader, walk,
  readHeaderSize, loadAsar };
