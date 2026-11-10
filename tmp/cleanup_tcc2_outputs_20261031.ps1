param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$roots = @('C:\GitHub\SHARC\sharc\campaigns\07_TCC2_DC_MSS_to_FS\output', 'D:\SHARC_outputs\07_TCC2_DC_MSS_to_FS')
$auditPath = 'C:\GitHub\SHARC\tmp\tcc2_output_cleanup_20261031.json'
$resultPath = 'C:\GitHub\SHARC\tmp\tcc2_output_cleanup_20261031_result.json'

function Assert-NoWorkers {
    $workers = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
        $_.CommandLine -match '07_TCC2_DC_MSS_to_FS' -and
        $_.CommandLine -match 'main_cli|run_multiple_campaigns'
    })
    if ($workers.Count) { throw 'Campaign workers are active; refusing deletion.' }
}

function Assert-Target($path) {
    $resolved = (Resolve-Path -LiteralPath $path).ProviderPath.TrimEnd('\')
    if ([IO.Path]::GetDirectoryName($resolved) -notin $roots) { throw "Outside campaign roots: $resolved" }
    $item = Get-Item -LiteralPath $resolved
    if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Unsafe target: $resolved" }
    if ($item.Name -notmatch '^output_tcc2_SA_noPY_(340|525)km_FS(20|40)m_LF(20|50)_Azi90_(HO\d+|PBO\d+km)_\d{4}-\d{2}-\d{2}_\d+$') { throw "Unexpected target name: $resolved" }
    $links = @(Get-ChildItem -LiteralPath $resolved -Force -Recurse | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint })
    if ($links.Count) { throw "Reparse point inside target: $resolved" }
    return $resolved
}

function Snapshot-Count($path) {
    $stream = [IO.File]::OpenRead($path)
    $gzip = [IO.Compression.GZipStream]::new($stream, [IO.Compression.CompressionMode]::Decompress)
    $reader = [IO.StreamReader]::new($gzip)
    try {
        $rows = @($reader.ReadToEnd() | ConvertFrom-Csv)
        for ($i=0; $i -lt $rows.Count; $i++) {
            if ([int]$rows[$i].snapshot_id -ne ($i+1)) { throw "Nonsequential snapshots: $path" }
        }
        return $rows.Count
    } finally { $reader.Dispose(); $gzip.Dispose(); $stream.Dispose() }
}

Assert-NoWorkers
$records = @(foreach ($root in $roots) {
    foreach ($folder in Get-ChildItem -LiteralPath $root -Directory | Sort-Object Name) {
        $manifestPath = Join-Path $folder.FullName 'tcc2_manifest.json'
        if (-not (Test-Path -LiteralPath $manifestPath)) { throw "Missing manifest: $folder" }
        $m = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        $mode = ($m.scenario -split '_')[-1]
        $action = 'keep'
        $reason = 'baseline or other output'
        $csvCount = $null
        if ($mode -match '^HO\d+$') { $action='delete'; $reason='all HO requested' }
        elseif ($mode -match '^PBO\d+km$') {
            $csvCount = Snapshot-Count (Join-Path $folder.FullName 'tcc2_snapshots.csv.gz')
            if ($m.complete) { $reason='completed PBO' }
            elseif ([int]$m.completed_snapshots -gt 9000 -or $csvCount -gt 9000) { $reason='incomplete PBO above 9000' }
            elseif ($csvCount -ne [int]$m.completed_snapshots) { throw "PBO count disagreement: $folder" }
            else { $action='delete'; $reason='incomplete PBO at most 9000' }
        }
        if ($action -eq 'delete') { $null = Assert-Target $folder.FullName }
        $files = @(Get-ChildItem -LiteralPath $folder.FullName -Recurse -File -Force | Sort-Object FullName | ForEach-Object {
            [pscustomobject]@{path=$_.FullName; bytes=$_.Length; modified=$_.LastWriteTimeUtc.Ticks}
        })
        [pscustomobject]@{path=$folder.FullName; name=$folder.Name; scenario=$m.scenario; mode=$mode;
            snapshots=[int]$m.completed_snapshots; csv_snapshots=$csvCount; complete=[bool]$m.complete;
            action=$action; reason=$reason; bytes=($files | Measure-Object bytes -Sum).Sum; files=$files}
    }
})
$audit = [pscustomobject]@{time=(Get-Date).ToString('o'); roots=$roots; records=$records}
if (-not $Apply) {
    if (Test-Path -LiteralPath $auditPath) { throw 'Audit already exists; do not overwrite.' }
    $audit | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $auditPath -Encoding utf8
} else {
    $before = Get-Content -LiteralPath $auditPath -Raw | ConvertFrom-Json
    if (($before.records | ConvertTo-Json -Depth 8 -Compress) -cne ($records | ConvertTo-Json -Depth 8 -Compress)) { throw 'Inventory changed since audit.' }
    Assert-NoWorkers
    $deleted = @()
    foreach ($record in $records | Where-Object action -eq 'delete') {
        $target = Assert-Target $record.path
        Remove-Item -LiteralPath $target -Recurse -Force
        if (Test-Path -LiteralPath $target) { throw "Deletion not completed: $target" }
        $deleted += $record.path
        Write-Output "Deleted: $target"
    }
    foreach ($record in $records | Where-Object action -eq 'keep') {
        foreach ($file in $record.files) {
            $actual = Get-Item -LiteralPath $file.path
            if ($actual.Length -ne $file.bytes -or $actual.LastWriteTimeUtc.Ticks -ne $file.modified) { throw "Preserved file changed: $($file.path)" }
        }
    }
    [pscustomobject]@{time=(Get-Date).ToString('o'); deleted=$deleted; preserved_files_verified=$true;
        removed_bytes=($records | Where-Object action -eq 'delete' | Measure-Object bytes -Sum).Sum} |
        ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $resultPath -Encoding utf8
}
$records | Select-Object action,mode,scenario,snapshots,csv_snapshots,complete,@{N='GiB';E={[math]::Round($_.bytes/1GB,3)}},path | ConvertTo-Json -Compress
