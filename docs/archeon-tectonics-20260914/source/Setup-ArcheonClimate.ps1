$ErrorActionPreference = 'Stop'
# This script never restarts Windows or modifies an existing distribution.
$taskDistro = 'ArcheonSim'
$taskSetup = (Join-Path $PSScriptRoot 'setup-archeon-linux.sh')
if (-not (Test-Path -LiteralPath $taskSetup)) { throw 'Linux setup source is missing.' }
$taskList = (& wsl.exe --list --quiet 2>&1 | Out-String).Replace([char]0, '').Trim()
if ($LASTEXITCODE -ne 0) { throw 'WSL cannot start. Restart Windows after VirtualMachinePlatform was enabled, then rerun this setup.' }
if (($taskList -split "`r?`n").Trim() -notcontains $taskDistro) {
    & wsl.exe --install --distribution Ubuntu --name $taskDistro --no-launch
    if ($LASTEXITCODE -ne 0) { throw 'The separate ArcheonSim distribution was not installed. No existing distribution was replaced.' }
}
$taskFullPath = [IO.Path]::GetFullPath($taskSetup)
$taskLinuxPath = '/mnt/' + $taskFullPath.Substring(0,1).ToLowerInvariant() + $taskFullPath.Substring(2).Replace('\','/')
& wsl.exe --distribution $taskDistro --user root --exec /bin/sh $taskLinuxPath
if ($LASTEXITCODE -ne 0) { throw 'The isolated Linux dependencies did not finish installing.' }
Write-Output 'ArcheonSim is ready. Climate runs use the unprivileged archeon account.'
