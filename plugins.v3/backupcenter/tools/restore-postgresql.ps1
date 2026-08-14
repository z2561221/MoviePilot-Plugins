param(
  [Parameter(Mandatory = $true)]
  [string]$Dump
)

$ErrorActionPreference = 'Stop'
$dumpPath = (Resolve-Path -LiteralPath $Dump).Path
if (-not (Get-Command pg_restore -ErrorAction SilentlyContinue)) {
  throw '未找到 pg_restore。请安装与目标 PostgreSQL 主版本兼容的客户端。'
}
foreach ($name in @('PGHOST', 'PGPORT', 'PGUSER', 'PGDATABASE', 'PGPASSWORD')) {
  if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) {
    throw "缺少环境变量 $name，停止恢复。"
  }
}

Write-Warning '确认 MoviePilot 已完全停止，并确认目标数据库允许清理和恢复。'
$confirmation = Read-Host '输入 RESTORE 继续'
if ($confirmation -cne 'RESTORE') {
  throw '未确认，未执行恢复。'
}

& pg_restore --host=$env:PGHOST --port=$env:PGPORT --username=$env:PGUSER --dbname=$env:PGDATABASE --clean --if-exists --no-owner --exit-on-error $dumpPath
if ($LASTEXITCODE -ne 0) {
  throw 'pg_restore 失败。请保留原数据库并按恢复教程回退。'
}
Write-Output 'PostgreSQL 恢复完成。现在启动 MoviePilot 并检查迁移与启动日志。'
