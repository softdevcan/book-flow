# Git AI live demo helper — book-flow
# Docs: https://usegitai.com/docs/cli
# Latest release (2026-06-14): v1.5.8
#
# Run from repo root:
#   scripts\git-ai-demo.cmd                    (AllSigned / GPO — use this)
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\git-ai-demo.ps1
#
# Optional flags:
#   -SkipInstall     Skip install/update step
#   -SkipCommit      Stop before demo commit (inspect working tree only)
#   -KeepBranch      Do not checkout back to previous branch after demo

param(
	[switch]$SkipInstall,
	[switch]$SkipCommit,
	[switch]$KeepBranch
)

$ErrorActionPreference = 'Stop'
$LatestVersion = 'v1.5.8'
$GitAiBin = Join-Path $HOME '.git-ai\bin'
$GitAiExe = Join-Path $GitAiBin 'git-ai.exe'
$DemoBranch = 'demo/git-ai-presentation'
$DemoFile = 'scripts/git-ai-demo-sample.py'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function Write-Step {
	param([string]$Title, [string]$Command)
	Write-Host ''
	Write-Host ('=' * 72) -ForegroundColor Cyan
	Write-Host $Title -ForegroundColor Cyan
	if ($Command) {
		Write-Host "  > $Command" -ForegroundColor DarkGray
	}
	Write-Host ('=' * 72) -ForegroundColor Cyan
}

function Invoke-Demo {
	param([string]$Command)
	Write-Host "`n>>> $Command`n" -ForegroundColor Yellow
	Invoke-Expression $Command
}

function Ensure-GitAi {
	if ($SkipInstall) { return }

	Write-Step '0. Install / update Git AI' "target: $LatestVersion"
	if (-not (Test-Path $GitAiBin)) {
		New-Item -ItemType Directory -Force -Path $GitAiBin | Out-Null
	}

	$versionOutput = ''
	if (Test-Path $GitAiExe) {
		$versionOutput = & $GitAiExe --version 2>&1 | Out-String
	}

	if ($versionOutput -notmatch [regex]::Escape($LatestVersion)) {
		Write-Host "Installing $LatestVersion ..."
		$installer = "https://github.com/git-ai-project/git-ai/releases/download/$LatestVersion/install.ps1"
		& powershell -NoProfile -ExecutionPolicy Bypass -Command "irm '$installer' | iex"
	} else {
		Write-Host "Already on $LatestVersion"
	}

	if (-not (Test-Path $GitAiExe)) {
		throw "git-ai.exe not found at $GitAiExe. Run install manually, then retry."
	}

	$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
	if ($userPath -notlike "*$GitAiBin*") {
		Write-Host "Adding $GitAiBin to user PATH (new terminals only)."
		[Environment]::SetEnvironmentVariable(
			'Path',
			"$GitAiBin;$userPath",
			'User'
		)
		$env:Path = "$GitAiBin;$env:Path"
	}
}

Set-Location $RepoRoot

Ensure-GitAi

Write-Step '1. Version & hooks' 'git ai --version; git ai install-hooks'
Invoke-Demo "git ai --version"
Invoke-Demo "git ai install-hooks"

$PreviousBranch = git rev-parse --abbrev-ref HEAD
$branchExists = git branch --list $DemoBranch
if ($branchExists) {
	git checkout $DemoBranch | Out-Null
} else {
	git checkout -b $DemoBranch | Out-Null
}

Write-Step '2. Baseline checkpoint (human)' 'git ai checkpoint'
Invoke-Demo 'git ai checkpoint'

@'
"""Sample module for Git AI demo — safe to delete after presentation."""

def greet(name: str) -> str:
	return f"Hello, {name}!"
'@ | Set-Content -Path $DemoFile -Encoding utf8

Write-Step '3. AI checkpoint (mock)' 'git ai checkpoint mock_ai'
Invoke-Demo 'git ai checkpoint mock_ai'

Write-Step '4. Working tree attribution' 'git ai status'
Invoke-Demo 'git ai status'

Write-Step '5. Working log detail' 'git ai checkpoint --show-working-log'
Invoke-Demo 'git ai checkpoint --show-working-log'

if ($SkipCommit) {
	Write-Host "`nSkipCommit set — demo stops before commit.`n" -ForegroundColor Green
	exit 0
}

Write-Step '6. Commit (attribution -> git note)' 'git add ...; git commit'
Invoke-Demo "git add $DemoFile"
Invoke-Demo 'git commit -m "demo: add git-ai sample module"'

Write-Step '7. Post-commit stats' 'git ai stats'
Invoke-Demo 'git ai stats'
Invoke-Demo 'git ai stats --json'

Write-Step '8. AI blame' "git ai blame $DemoFile"
Invoke-Demo "git ai blame $DemoFile"

Write-Step '9. Annotated diff' 'git ai diff HEAD'
Invoke-Demo 'git ai diff HEAD'

Write-Step '10. Raw authorship note' 'git ai show HEAD'
Invoke-Demo 'git ai show HEAD'

Write-Step '11. Git log with AI notes' 'git log --show-notes=ai -1'
Invoke-Demo 'git log --show-notes=ai -1'

Write-Step '12. Repo-wide stats (optional, may be slow)' `
	'git ai stats 4b825dc642cb6eb9a060e54bf8d69288fbee4904..HEAD'
Write-Host 'Skipped by default — uncomment in script for large repos.' -ForegroundColor DarkGray

if (-not $KeepBranch) {
	git checkout $PreviousBranch | Out-Null
	Write-Host "`nReturned to branch: $PreviousBranch" -ForegroundColor Green
	Write-Host "Demo branch kept as: $DemoBranch (delete with git branch -D $DemoBranch)" `
		-ForegroundColor DarkGray
}

Write-Host "`nDemo complete.`n" -ForegroundColor Green
