#requires -Version 5.1
<#
  Read-only snapshot of the ACTIVE Inventor assembly's TOP-LEVEL occurrences.
  Prefer ipt-mcp inventory when available. This is a fallback if the agent cannot
  convert ipt-mcp's variable response format into the normalized JSON contract.
#>
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$OutFile)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$dest=[IO.Path]::GetFullPath($OutFile)
if (Test-Path $dest) {throw "防止覆寫：$dest 已存在"}
$app=[Runtime.InteropServices.Marshal]::GetActiveObject('Inventor.Application')
$doc=$app.ActiveDocument
if ($null -eq $doc -or [int]$doc.DocumentType -ne 12291) {throw '請先在 Inventor 中開啟 IAM 組立文件'}
$source=[string]$doc.FullFileName
if (![IO.Path]::IsPathRooted($source) -or !(Test-Path $source)) {throw '組立文件必須先儲存'}
$entries=New-Object System.Collections.ArrayList
$occ=$doc.ComponentDefinition.Occurrences
for ($i=1;$i -le $occ.Count;$i++) {
    $o=$occ.Item($i)
    $id=[string]$o.Name
    if ([string]::IsNullOrWhiteSpace($id)) {throw '存在無名稱的 occurrence'}
    [void]$entries.Add(@{id=$id;name=$id;scope='top_level';source='inventor-api-readonly';confidence='verified'})
}
if ($entries.Count -eq 0) {throw '組立為空'}
$payload=@{
    model_path=$source
    provenance='Inventor 2027 active assembly top-level occurrence read-only snapshot'
    components=@($entries.ToArray())
}
$parent=Split-Path $dest -Parent
if (!(Test-Path $parent)) {New-Item -ItemType Directory -Path $parent -Force | Out-Null}
$payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $dest -Encoding UTF8
Write-Host "已建立候選資料 snapshot: $dest；occurrences: $($entries.Count)"
Write-Warning '僅頂層零件清單；不是裝配順序，也未驗證干涉或安裝方向。'
