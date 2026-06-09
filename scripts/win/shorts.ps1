<#
.SYNOPSIS
  Windows entry point — runs the (Linux) lifecycle scripts inside WSL2.

.DESCRIPTION
  The whole stack runs inside one WSL2 distro (ADR 0013): ComfyUI + Ollama (GPU plane,
  CUDA via the NVIDIA Windows driver) and Docker + kind + Argo (control plane). This
  wrapper just dispatches into WSL so it feels native from PowerShell; the bash scripts
  under scripts/ stay the single source of truth — there is no PowerShell reimplementation.

.PARAMETER Command
  up | down | trigger   (forwarded to scripts/<command>.sh)

.PARAMETER Args
  Extra args passed through (e.g. --dry-run, --profiles finance,business, --purge).

.EXAMPLE
  .\scripts\win\shorts.ps1 up
  .\scripts\win\shorts.ps1 trigger --dry-run
  .\scripts\win\shorts.ps1 down --purge

.NOTES
  Set the distro with $env:WSL_DISTRO if it isn't your default (e.g. "Ubuntu").
  The repo must live on the WSL2 ext4 filesystem (NOT /mnt/c) — see ADR 0013 D3.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [ValidateSet('up', 'down', 'trigger')]
  [string]$Command,

  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Args
)

$ErrorActionPreference = 'Stop'

# Locate the repo root inside WSL: this script lives at scripts/win/, so root is ../../ .
# We resolve it as a WSL path via `wslpath` so it works regardless of where the repo lives.
$winRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

$distroArgs = @()
if ($env:WSL_DISTRO) { $distroArgs = @('-d', $env:WSL_DISTRO) }

# Translate the Windows repo path to a WSL path; warn loudly if it's on /mnt/ (slow I/O, ADR 0013 D3).
$wslRoot = (& wsl @distroArgs wslpath "$winRoot").Trim()
if ($wslRoot -like '/mnt/*') {
  Write-Warning "Repo is on a Windows drive ($wslRoot). Move it onto the WSL2 ext4 filesystem — /mnt/* I/O will throttle the artifact bus (ADR 0013 D3)."
}

$passthrough = ($Args -join ' ')
$bash = "cd '$wslRoot' && ./scripts/$Command.sh $passthrough"

Write-Host "wsl $($distroArgs -join ' ') -- bash -lc `"$bash`"" -ForegroundColor DarkCyan
& wsl @distroArgs -- bash -lc "$bash"
exit $LASTEXITCODE
