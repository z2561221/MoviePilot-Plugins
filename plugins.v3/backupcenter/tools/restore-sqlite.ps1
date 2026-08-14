param(
  [Parameter(Mandatory = $true)]
  [string]$Snapshot,
  [Parameter(Mandatory = $true)]
  [string]$TargetDatabase
)

$ErrorActionPreference = 'Stop'
$snapshotPath = (Resolve-Path -LiteralPath $Snapshot).Path
$targetPath = [IO.Path]::GetFullPath($TargetDatabase)
if (-not (Test-Path -LiteralPath $snapshotPath -PathType Leaf)) {
  throw 'SQLite 快照不存在。'
}

Write-Warning '确认 MoviePilot 已完全停止。此脚本将替换目标 user.db。'
$confirmation = Read-Host '输入 RESTORE 继续'
if ($confirmation -cne 'RESTORE') {
  throw '未确认，未执行恢复。'
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$targetDirectory = Split-Path -Parent $targetPath
if (-not (Test-Path -LiteralPath $targetDirectory -PathType Container)) {
  throw '目标数据库目录不存在。'
}
$temporaryPath = Join-Path $targetDirectory ".backupcenter-restore-$timestamp.tmp"
foreach ($suffix in @('', '-wal', '-shm')) {
  $path = "$targetPath$suffix"
  if (Test-Path -LiteralPath $path -PathType Leaf) {
    Copy-Item -LiteralPath $path -Destination "$path.pre-backupcenter-$timestamp" -Force
  }
}
try {
  Copy-Item -LiteralPath $snapshotPath -Destination $temporaryPath -Force
  if (Test-Path -LiteralPath $targetPath -PathType Leaf) {
    [IO.File]::Replace($temporaryPath, $targetPath, $null, $true)
  } else {
    [IO.File]::Move($temporaryPath, $targetPath)
  }
  Remove-Item -LiteralPath "$targetPath-wal", "$targetPath-shm" -Force -ErrorAction SilentlyContinue
} finally {
  Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
}
Write-Output 'SQLite 快照已替换。现在启动 MoviePilot 并检查迁移与启动日志。'
