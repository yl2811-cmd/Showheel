$ErrorActionPreference = 'Stop'
$auditRoot = 'D:\SKBS\review\tectonics-archive-20260914'
$sourceRoot = [IO.Path]::GetFullPath('D:\SKBS\review\tectonics-20260914')
$archiveRoot = [IO.Path]::GetFullPath('D:\SKBS\archives\pending-manual-delete-20260914\tectonics-early-rounds')
$manifest = Get-Content -LiteralPath (Join-Path $auditRoot 'manifest.json') -Raw | ConvertFrom-Json
$pending = @($manifest.folders | Where-Object { Test-Path -LiteralPath $_.destination })
if (Get-Process -Name python,pythonw -ErrorAction SilentlyContinue) { throw 'Python process is active; inspect before restoring' }
foreach ($folder in $pending) {
    $from = (Resolve-Path -LiteralPath $folder.destination).Path
    $to = [IO.Path]::GetFullPath($folder.source)
    if ([IO.Path]::GetDirectoryName($from) -ne $archiveRoot -or [IO.Path]::GetDirectoryName($to) -ne $sourceRoot) { throw 'Restore path outside approved roots' }
    if (Test-Path -LiteralPath $to) { throw "Original path already exists; will not overwrite: $to" }
    if ((Get-Item -LiteralPath $from).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked source' }
    $children = @(Get-ChildItem -LiteralPath $from -Recurse -Force)
    if ($children | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }) { throw 'Linked archive child' }
    if (@($children | Where-Object {-not $_.PSIsContainer}).Count -ne $folder.files) { throw 'Archive file set changed' }
    foreach ($entry in @($manifest.files | Where-Object directory -eq $folder.name)) {
        if ((Get-FileHash -LiteralPath $entry.destination -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) { throw "Archive file changed: $($entry.destination)" }
    }
}
foreach ($folder in $pending) {
    Move-Item -LiteralPath $folder.destination -Destination $folder.source
    Write-Output "Restored $($folder.name)"
}
