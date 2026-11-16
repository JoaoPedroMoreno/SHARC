$ErrorActionPreference = 'Stop'
$sourceRoot = [IO.Path]::GetFullPath('C:\GitHub\SHARC\sharc\campaigns\07_TCC2_DC_MSS_to_FS\output').TrimEnd('\')
$destRoot = [IO.Path]::GetFullPath('D:\SHARC_outputs\07_TCC2_DC_MSS_to_FS').TrimEnd('\')
$reportPath = 'C:\GitHub\SHARC\reports\tcc07_migration_20261116.json'
$folders = @(Get-ChildItem -LiteralPath $sourceRoot -Directory)
$report = [ordered]@{ source = $sourceRoot; destination = $destRoot; started = (Get-Date).ToString('o'); folders = @() }
foreach ($folder in $folders) {
    if ($folder.Name -notmatch '^output_tcc2_SA_noPY_(340|525)km_FS(20|40)m_LF(20|50)_Azi90_(BASELINE|PBO\d+km)_\d{4}-\d{2}-\d{2}_\d+$') { throw "Unexpected folder: $($folder.FullName)" }
    if ($folder.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Source is a reparse point' }
    $src = [IO.Path]::GetFullPath($folder.FullName)
    $dst = [IO.Path]::GetFullPath((Join-Path $destRoot $folder.Name))
    if ([IO.Path]::GetDirectoryName($src) -ne $sourceRoot -or [IO.Path]::GetDirectoryName($dst) -ne $destRoot) { throw 'Path outside approved roots' }
    if (Test-Path -LiteralPath $dst) { throw "Destination already exists: $dst" }
    $manifest = Get-Content -LiteralPath (Join-Path $src 'tcc2_manifest.json') -Raw | ConvertFrom-Json
    if (-not $manifest.complete -or $manifest.completed_snapshots -ne 10000) { throw "Source is incomplete: $src" }
    $entries = @(Get-ChildItem -LiteralPath $src -Recurse -Force)
    if (@($entries | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) { throw 'Reparse point inside output' }
}
foreach ($folder in $folders) {
    $src = [IO.Path]::GetFullPath($folder.FullName)
    $dst = [IO.Path]::GetFullPath((Join-Path $destRoot $folder.Name))
    Write-Output "Copying $($folder.Name)"
    Copy-Item -LiteralPath $src -Destination $dst -Recurse
    $files = @(Get-ChildItem -LiteralPath $src -Recurse -File -Force)
    $destFiles = @(Get-ChildItem -LiteralPath $dst -Recurse -File -Force)
    if ($files.Count -ne $destFiles.Count) { throw "File count mismatch: $dst" }
    $checks = @()
    foreach ($file in $files) {
        $relative = $file.FullName.Substring($src.Length + 1)
        $target = Join-Path $dst $relative
        $sourceHash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
        $targetHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
        $fresh = Get-Item -LiteralPath $file.FullName
        if ($sourceHash -ne $targetHash -or $fresh.Length -ne $file.Length -or $fresh.LastWriteTimeUtc -ne $file.LastWriteTimeUtc) { throw "File changed or hash mismatch: $relative" }
        $checks += [ordered]@{ path = $relative; bytes = $file.Length; sha256 = $sourceHash }
    }
    $report.folders += [ordered]@{ source = $src; destination = $dst; verified = $true; source_removed = $false; files = $checks }
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportPath -Encoding utf8
    # Recheck absolute targets immediately before the only destructive operation.
    if ([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($src)) -ne $sourceRoot -or $src -eq $sourceRoot -or -not (Test-Path -LiteralPath $dst)) { throw 'Deletion guard failed' }
    Remove-Item -LiteralPath $src -Recurse -Force
    $report.folders[-1].source_removed = $true
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportPath -Encoding utf8
    Write-Output "Verified SHA256 and moved $($folder.Name)"
}
$report.completed = (Get-Date).ToString('o')
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportPath -Encoding utf8
Write-Output "Finished: $($folders.Count) folders. Journal: $reportPath"
