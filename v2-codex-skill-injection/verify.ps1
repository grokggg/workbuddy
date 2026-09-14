#Requires -Version 5.1
<#
.SYNOPSIS
    v2-codex-skill-injection 验证脚本（Windows PowerShell）
.DESCRIPTION
    三层校验：
      1. kit 自身资产   —— assets 里的 SKILL.md / references 在不在
      2. 安装点         —— skills 目录、SKILL.md 结构、探针 token、profile 块
      3. 自读探针判据   —— 把模型刚才的回答传进来，判定 SKILL.md 是否真被加载

    逻辑在 cli.py + lib/injector.py，与 verify.sh 共用。

    ⚠ 实机状态：本脚本在 Linux 沙箱内**未经运行**（无 PowerShell 环境）。
    语法按 PowerShell 5.1 编写，但请以实机结果为准。
.EXAMPLE
    .\verify.ps1
    .\verify.ps1 -Framework all
    .\verify.ps1 -Probe "自读探针：VCP-XXXXXXXX"
#>
[CmdletBinding()]
param(
    [ValidateSet('codex','claude-code','cursor','generic','all')]
    [string]$Framework = 'codex',
    [string]$Probe
)

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Definition

function Find-Python {
    foreach ($name in @('python3', 'python', 'py')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        try {
            $out = & $cmd.Source -c 'print(1)' 2>$null
            if ($out -eq '1') { return $cmd.Source }
        } catch { continue }
    }
    return $null
}

$py = Find-Python
if (-not $py) {
    Write-Host '需要 Python 3.8+。' -ForegroundColor Red
    exit 1
}

$cliArgs = @("$Here\cli.py", 'verify', '--framework', $Framework)
if ($Probe) { $cliArgs += @('--probe', $Probe) }

& $py @cliArgs
exit $LASTEXITCODE
