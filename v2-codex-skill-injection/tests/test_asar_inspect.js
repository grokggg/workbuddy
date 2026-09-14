/**
 * asar_inspect.js 单元测试
 *
 * 不依赖 @electron/asar 的部分（list / info / 头解析）直接测；
 * extract 依赖模块，模块缺失时 skip 而不是 fail —— 它是可选依赖。
 *
 * 跑法：node tests/test_asar_inspect.js
 */
'use strict';

const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');

const ROOT = path.dirname(__dirname);
const TOOL = path.join(ROOT, 'tools', 'asar_inspect.js');
const M = require(TOOL);

let passed = 0;
let failed = 0;
let skipped = 0;

function test(name, fn) {
  try {
    fn();
    passed++;
    process.stdout.write(`  ok   ${name}\n`);
  } catch (e) {
    failed++;
    process.stdout.write(`  FAIL ${name}\n       ${e.message}\n`);
  }
}

function skip(name, why) {
  skipped++;
  process.stdout.write(`  skip ${name}（${why}）\n`);
}

// ---------------------------------------------------------------- 造一个 asar
function makeAsar(dir) {
  // 用工具自己的 loadAsar()，而不是硬 require 一条 node_modules 路径 ——
  // 后者在模块装在别处（或走 NODE_PATH）时会误判成"模块缺失"。
  const asar = M.loadAsar();
  assert.ok(asar, '需要 @electron/asar：npm install @electron/asar');
  const src = path.join(dir, 'src');
  fs.mkdirSync(path.join(src, 'lib'), { recursive: true });
  fs.writeFileSync(path.join(src, 'package.json'),
    JSON.stringify({ name: 'demo-app', version: '4.2.0', main: 'main.js' }));
  fs.writeFileSync(path.join(src, 'main.js'), 'console.log(1);\n');
  fs.writeFileSync(path.join(src, 'lib', 'util.js'), 'exports.x=1;\n');
  const out = path.join(dir, 'app.asar');
  return asar.createPackage(src, out).then(() => out);
}

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'vcsi-asar-'));
const hasModule = !!M.loadAsar();
let asarFile = null;

// createPackage 是异步的（返回 Promise），extractAll 是同步的。
// 造 fixture 必须 await，否则后面的断言会撞上"文件还没写出来"。
async function buildFixture() {
  if (!hasModule) return null;
  return makeAsar(tmp);
}

async function main() {
asarFile = await buildFixture();

process.stdout.write('\n== 头解析与结构 ==\n');

test('asar fixture 造出来了', () => {
  assert.ok(asarFile && fs.existsSync(asarFile), 'createPackage 没产出文件');
});

test('parseHeader 能解析出 files', () => {
  if (!asarFile) throw new Error('前置失败');
  const h = M.parseHeader(asarFile);
  assert.ok(h.files, 'header 应有 files');
  assert.ok(h.files['package.json'], '应有 package.json');
});

test('walk 产出带子目录的完整路径', () => {
  if (!asarFile) throw new Error('前置失败');
  const h = M.parseHeader(asarFile);
  const out = [];
  M.walk(h, '', out);
  const paths = out.map((e) => e.path);
  // 前导斜杠是 walk 的约定，但 @electron/asar 的 extractFile 不接受 —— 见下方回归
  assert.ok(paths.includes('/package.json'), paths.join(','));
  assert.ok(paths.some((p) => p.includes('lib')), paths.join(','));
});

test('list 统计文件数与字节数', () => {
  if (!asarFile) throw new Error('前置失败');
  const r = M.cmdList(asarFile);
  assert.strictEqual(r.files, 3, `期望 3 个文件，实得 ${r.files}`);
  assert.ok(r.bytes > 0);
});

test('info 读出 package.json 的 name/version/main', () => {
  if (!asarFile) throw new Error('前置失败');
  const r = M.cmdInfo(asarFile);
  assert.ok(r.package, `package 读不出来：${r.packageError || '无'}`);
  assert.strictEqual(r.package.name, 'demo-app');
  assert.strictEqual(r.package.version, '4.2.0');
  assert.strictEqual(r.package.main, 'main.js');
});

test('info 在模块缺失时给出 asarModule=missing 且不抛', () => {
  if (!asarFile) throw new Error('前置失败');
  const r = M.cmdInfo(asarFile);
  assert.ok(['available', 'missing'].includes(r.asarModule));
  if (r.asarModule === 'missing') {
    // 读不出来必须把原因带出来，不能静默给 null
    assert.ok(r.packageError || r.package === null);
  }
});

process.stdout.write('\n== 范围约束 ==\n');

test('只暴露 list/extract/info 三个动作', () => {
  const src = fs.readFileSync(TOOL, 'utf8');
  assert.ok(/const ACTIONS = \['list', 'extract', 'info'\]/.test(src),
    'ACTIONS 白名单被改动了');
});

test('源码里不含 pack/createPackage（不做写回/打包）', () => {
  const src = fs.readFileSync(TOOL, 'utf8');
  assert.ok(!/createPackage|pack\(/.test(src),
    '出现了打包能力，超出本工具范围');
});

test('未知动作会报错而不是静默执行', () => {
  assert.throws(
    () => M.main(['patch', asarFile || '/dev/null']),
    /未知动作/);
});

test('文件不存在会报错', () => {
  const p = path.join(tmp, 'nope.asar');
  assert.throws(() => M.main(['list', p]), /文件不存在/);
});

process.stdout.write('\n== CLI ==\n');

test('--help 退出码 0', () => {
  const out = execFileSync(process.execPath, [TOOL, '--help'],
    { encoding: 'utf8' });
  assert.ok(out.includes('用法'));
});

test('CLI list 正常输出', () => {
  if (!asarFile) throw new Error('前置失败');
  const out = execFileSync(process.execPath, [TOOL, 'list', asarFile],
    { encoding: 'utf8' });
  assert.ok(out.includes('package.json'), out);
});

test('CLI 未知动作退出码非 0', () => {
  let code = 0;
  try {
    execFileSync(process.execPath, [TOOL, 'frobnicate', '/dev/null'],
      { encoding: 'utf8', stdio: 'pipe' });
  } catch (e) {
    code = e.status;
  }
  assert.notStrictEqual(code, 0);
});

process.stdout.write('\n== extract（依赖可选模块）==\n');

if (hasModule && asarFile) {
  test('extract 解出全部文件', () => {
    const outDir = path.join(tmp, 'out');
    const r = M.cmdExtract(asarFile, outDir);
    assert.strictEqual(r.files, 3, `期望 3 个，实得 ${r.files}`);
    assert.ok(fs.existsSync(path.join(outDir, 'package.json')));
    assert.ok(fs.existsSync(path.join(outDir, 'lib', 'util.js')));
  });

  test('extract 默认落到工作目录（不原地改）', () => {
    const before = fs.statSync(asarFile).mtimeMs;
    M.cmdExtract(asarFile);
    assert.strictEqual(fs.statSync(asarFile).mtimeMs, before,
      '原 asar 不应被改动');
  });
} else {
  skip('extract 解出全部文件', '缺 @electron/asar');
  skip('extract 默认落到工作目录', '缺 @electron/asar');
}

fs.rmSync(tmp, { recursive: true, force: true });

process.stdout.write(
  `\n通过 ${passed} / 失败 ${failed} / 跳过 ${skipped}\n`);
process.exit(failed ? 1 : 0);
}

main().catch((e) => {
  process.stderr.write('测试崩溃：' + e.stack + '\n');
  process.exit(1);
});
