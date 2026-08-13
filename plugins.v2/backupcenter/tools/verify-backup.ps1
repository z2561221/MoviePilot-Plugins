param(
  [Parameter(Mandatory = $true)]
  [string]$BackupRoot
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $BackupRoot).Path
$checksumPath = Join-Path $root 'checksums.sha256'
if (-not (Test-Path -LiteralPath $checksumPath -PathType Leaf)) {
  throw '缺少 checksums.sha256，停止校验。'
}

$verified = 0
foreach ($line in Get-Content -LiteralPath $checksumPath) {
  if ([string]::IsNullOrWhiteSpace($line)) { continue }
  if ($line -notmatch '^([0-9a-f]{64})  (.+)$') {
    throw '校验清单格式无效，停止校验。'
  }
  $expected = $Matches[1]
  $relativePath = $Matches[2]
  if ([IO.Path]::IsPathRooted($relativePath) -or $relativePath.Contains(':') -or $relativePath -match '(^|[\\/])\.\.([\\/]|$)') {
    throw '校验清单包含不安全路径，停止校验。'
  }
  $target = Join-Path $root $relativePath
  if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
    throw "备份文件缺失：$relativePath"
  }
  $actual = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $expected) {
    throw "哈希不匹配：$relativePath"
  }
  $verified++
}

if ($verified -eq 0) { throw '校验清单为空，停止恢复。' }
Write-Output "校验通过：$verified 个文件。"
