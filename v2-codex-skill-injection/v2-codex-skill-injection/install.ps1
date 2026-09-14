#Requires -Version 5.1
<#
.SYNOPSIS
    v2-codex-skill-injection 安装脚本（Windows PowerShell）
.DESCRIPTION
    复现 BV15y3U6oEmt（by茶，197s）的 Codex Skill 目录注入。
    视频原环境就是 Windows PowerShell，所以提供本脚本。

    落盘位置（视频实测）：C:\Users\<你>\codex\skills\veni-coldbrew\SKILL.md
    若已存在 C:\Users\<你>\.codex\skills 则用那个 —— 两个都认。

    本脚本是薄封装，逻辑在 cli.py + lib/injector.py，与 install.sh 共用同一份，
    避免同一套规则在 bash 与 PowerShell 里各写一遍然后行为不一致。

    ⚠ 实机状态：本脚本在 Linux 沙箱内**未经运行**（无 PowerShell 环境）。
    语法按 PowerShell 5.1 编写，但请以实机结果为准。
.EXAMPLE
    .\install.ps1
    .\install.ps1 -Framework all
    .\install.ps1 -DryRun
    .\install.ps1 -Uninstall
    .\install.ps1 -Force
    .\install.ps1 -WithNodeDeps
#>
[CmdletBinding()]
param(
    [ValidateSet('codex','claude-code','cursor','generic','all')]
    [string]$Framework = 'codex',
    [switch]$DryRun,
    [switch]$Uninstall,
    [switch]$Force,
    [switch]$WithNodeDeps
)

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Definition

# ---------------------------------------------------------------- 找 python
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
    Write-Host '需要 Python 3.8+。装完再跑，或改用 install.sh（Git Bash / WSL）。' -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------- 组参数
$sub = if ($Uninstall) { 'uninstall' } else { 'install' }
$cliArgs = @("$Here\cli.py", $sub, '--framework', $Framework)
if ($DryRun)  { $cliArgs += '--dry-run' }
if ($Force)   { $cliArgs += '--force' }

& $py @cliArgs
$code = $LASTEXITCODE

# ---------------------------------------------------------------- 可选依赖
if ($WithNodeDeps) {
    Write-Host "`n装 @electron/asar（asar 解包用，可选）" -ForegroundColor Cyan
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        Push-Location $Here
        & npm install @electron/asar --no-audit --no-fund
        Pop-Location
    } else {
        Write-Host '  [skip] 没找到 npm。用 npx --yes @electron/asar 也能跑 extract。'
    }
} elseif (-not $Uninstall) {
    Write-Host "`n提示：asar 解包需要 @electron/asar。" -ForegroundColor Yellow
    Write-Host '      跑 .\install.ps1 -WithNodeDeps 装，或用 npx 临时拉。'
}

exit $code
