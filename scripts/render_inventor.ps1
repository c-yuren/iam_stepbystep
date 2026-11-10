#requires -Version 5.1
<#
.PURPOSE
  Proof-of-concept native Inventor DWG + PDF adapter for cumulative top-level steps.
  Test on a disposable, simple .iam before using with real work.
  Requires Windows PowerShell 5.1, Inventor 2027 running, standard template.
  Does not change or save the original .iam; creates a SaveCopyAs workspace .iam.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$JobDir,
    [string]$TemplatePath = ""
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Checkpoint([string]$stage,[string]$detail) {
    @{stage=$stage; detail=$detail; at=[DateTime]::UtcNow.ToString("o")} |
      ConvertTo-Json -Depth 10 | Set-Content -Path (Join-Path $job "checkpoint.json") -Encoding UTF8
}
function Add-Note($sheet, $app, [double]$x, [double]$y, [string]$text) {
    $pos = $app.TransientGeometry.CreatePoint2d($x, $y)
    $null = $sheet.DrawingNotes.GeneralNotes.AddFitted($pos, $text)
}

$job = [IO.Path]::GetFullPath($JobDir)
$planPath = Join-Path $job "plan.json"
if (!(Test-Path $planPath -PathType Leaf)) {throw "找不到 plan.json"}
$plan = Get-Content $planPath -Raw -Encoding UTF8 | ConvertFrom-Json
$planHash = (Get-FileHash $planPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($plan.schema_version -ne 1) {throw "不支援的 plan schema"}
$source = [IO.Path]::GetFullPath([string]$plan.source.model_path)
if (!(Test-Path $source -PathType Leaf) -or !($source.ToLowerInvariant().EndsWith(".iam"))) {throw "必須提供存在的 .iam 原始檔"}
$jobPrefix = $job.TrimEnd('\') + '\'
if ($source.StartsWith($jobPrefix,[StringComparison]::OrdinalIgnoreCase)) {throw "來源不應位於本次輸出目錄中"}
if ($plan.settings.paper -notin @('A3','A4')) {throw "MVP 僅支援 A3/A4"}
if ($plan.settings.orientation -notin @('landscape','portrait')) {throw "不支援的紙張方向"}
foreach ($step in $plan.steps) {
    if ($step.visual.mode -ne 'cumulative' -or $step.visual.camera -ne 'iso') {
        throw "MVP 不支援 $($step.id) 的視圖模式；不得悄悄退回其他風格"
    }
}
if (!(Test-Path $job -PathType Container)) {throw "工作區不存在"}
$work = Join-Path $job 'working'
$out = Join-Path $job 'output'
New-Item -Path $work,$out -ItemType Directory -Force | Out-Null
$copy = Join-Path $work 'Assembly_WorkingCopy.iam'
$dwg = Join-Path $out 'Assembly_Instructions.dwg'
$pdf = Join-Path $out 'Assembly_Instructions.pdf'
foreach ($path in @($copy,$dwg,$pdf,(Join-Path $job 'result.json'))) {
    if (Test-Path $path) {throw "防止覆寫：$path 已存在。請建立新任務或先備份。"}
}
# One CAD writer per job; released on error too.
$lock = Join-Path $job '.inventor-write.lock'
$lockStream = [IO.File]::Open($lock,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
$originalHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
$workDoc = $null; $drawing = $null
try {
    Write-Checkpoint 'starting' 'Connecting to running Inventor 2027'
    # Windows PowerShell 5.1 / .NET Framework exposes Marshal.GetActiveObject.
    $app = [Runtime.InteropServices.Marshal]::GetActiveObject('Inventor.Application')
    if ([int]$app.SoftwareVersion.Major -lt 1) {throw "無法確認 Inventor 狀態"}
    # Probe actual running Inventor release by display version at user's workstation.
    $original = $app.Documents.Open($source,$false)
    if ([int]$original.DocumentType -ne 12291) {throw "不是 AssemblyDocument"}
    # SaveCopyAs=True: preserves original source document. Child parts remain referenced,
    # so use Pack and Go separately before distributing the drawing to another computer.
    $original.SaveAs($copy,$true)
    if (!(Test-Path $copy)) {throw "SaveCopyAs 未建立工作副本"}
    $workDoc = $app.Documents.Open($copy,$true)
    if (![string]::Equals([string]$workDoc.FullFileName,$copy,[StringComparison]::OrdinalIgnoreCase)) {
        throw "Inventor 目前開啟的不是指定工作副本"
    }
    Write-Checkpoint 'workcopy' 'Created isolated assembly copy'

    $occ = @{}
    $occurrences = $workDoc.ComponentDefinition.Occurrences
    for ($i=1; $i -le $occurrences.Count; $i++) {
        $item = $occurrences.Item($i)
        if ($occ.ContainsKey([string]$item.Name)) {throw "同層 occurrence 名稱不唯一"}
        $occ[[string]$item.Name] = $item
    }
    foreach ($c in $plan.components) {
        if (!$occ.ContainsKey([string]$c.id)) {
            throw "MVP 僅支援頂層 occurrence，找不到 $($c.id)；請確認 snapshot 與工作副本一致"
        }
    }
    $installed = New-Object 'System.Collections.Generic.HashSet[string]'
    $views = $workDoc.ComponentDefinition.RepresentationsManager.DesignViewRepresentations
    foreach ($s in $plan.steps) {
        foreach ($id in $s.add) { if (!$occ.ContainsKey([string]$id)) {throw "未知 occurrence: $id"}; $null=$installed.Add([string]$id) }
        $repName = 'AI_' + [string]$s.id
        $rep = $views.Add($repName,$false)
        $rep.Activate()
        $rep.HideAll()
        foreach ($id in $installed) {$occ[$id].Visible = $true}
        $rep.Locked = $true
    }
    $workDoc.Save()
    Write-Checkpoint 'design_views' 'Completed cumulative Design View Representations'

    if ($TemplatePath) {
        if (!(Test-Path $TemplatePath -PathType Leaf)) {throw "圖框範本不存在：$TemplatePath"}
        $drawing = $app.Documents.Add(12292,[IO.Path]::GetFullPath($TemplatePath),$true)
    } else {
        $drawing = $app.Documents.Add(12292,"",$true)
    }
    $n = 0
    foreach ($s in $plan.steps) {
        $n += 1
        $sheet = if ($n -eq 1) {$drawing.Sheets.Item(1)} else {$drawing.Sheets.Add()}
        $sheet.Activate()
        $sheet.Size = if ($plan.settings.paper -eq 'A3') {9996} else {9997}
        $sheet.Orientation = if ($plan.settings.orientation -eq 'landscape') {10242} else {10243}
        $sheet.Name = [string]$s.id
        $pt = $app.TransientGeometry.CreatePoint2d([double]$sheet.Width/2,[double]$sheet.Height*0.52)
        $opt = $app.TransientObjects.CreateNameValueMap()
        $opt.Add('DesignViewRepresentation','AI_' + [string]$s.id)
        $opt.Add('DesignViewAssociative',$true)
        $view = $sheet.DrawingViews.AddBaseView($workDoc,$pt,0.15,10759,32258,'',[Type]::Missing,$opt)
        $maxW = [double]$sheet.Width*0.84
        $maxH = [double]$sheet.Height*0.67
        if ([double]$view.Width -gt 0 -and [double]$view.Height -gt 0) {
            $factor = [Math]::Min($maxW/[double]$view.Width,$maxH/[double]$view.Height)
            $view.Scale = [Math]::Min(4.0,[double]$view.Scale*$factor)
        }
        $view.Center = $pt
        Add-Note $sheet $app 1 ([double]$sheet.Height-1) ("STEP " + $s.id + " - " + $s.title)
        Add-Note $sheet $app 1 2 ("Add: " + ($s.add -join ', '))
        if (!$s.review.approved) {
            Add-Note $sheet $app 1 1 'DRAFT - ENGINEERING REVIEW REQUIRED'
        }
    }
    $drawing.Update()
    $drawing.SaveAsInventorDWG($dwg,$false)
    if (!(Test-Path $dwg)) {throw "Inventor DWG 未成功儲存"}
    Write-Checkpoint 'dwg' 'Saved native Inventor DWG'

    $pdfAddIn = $app.ApplicationAddIns.ItemById('{0AC6FD96-2F4D-42CE-8BE0-8AEA580399E4}')
    $context = $app.TransientObjects.CreateTranslationContext()
    $context.Type = 13059  # kFileBrowseIOMechanism
    $options = $app.TransientObjects.CreateNameValueMap()
    if ($pdfAddIn.HasSaveCopyAsOptions($drawing,$context,$options)) {
        try { $options.Value['Sheet_Range'] = 14082 } catch { $options.Add('Sheet_Range',14082) }
        try { $options.Value['Vector_Resolution'] = 400 } catch { $options.Add('Vector_Resolution',400) }
    }
    $data = $app.TransientObjects.CreateDataMedium()
    $data.FileName = $pdf
    $pdfAddIn.SaveCopyAs($drawing,$context,$options,$data)
    if (!(Test-Path $pdf)) {throw "PDF 未成功產生"}
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $originalHash) {
        throw "安全檢查失敗：原始 IAM 發生改變。請檢查並勿發布成果。"
    }
    if ((Get-FileHash $planPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $planHash) {
        throw '生成期間組裝計畫發生變更，請勿發布這份成果'
    }
    # These are technical artifacts only; no claim that assembly paths are valid.
    $result = @{
        status='Draft'; plan_sha256=$planHash; adapter='inventor-powershell-mvp'; exported_at=[DateTime]::UtcNow.ToString('o');
        workcopy=$copy; sheets=$plan.steps.Count;
        artifacts=@{
            dwg=@{path=$dwg;sha256=(Get-FileHash $dwg -Algorithm SHA256).Hash}
            pdf=@{path=$pdf;sha256=(Get-FileHash $pdf -Algorithm SHA256).Hash}
        }
        limitations=@('Top-level occurrences only','Cumulative isometric drawing only',
           'No assembly trajectory validation','No arrow or exploded-view generation',
           'Verify linked model references and PDF sheet count manually')
    }
    $result | ConvertTo-Json -Depth 12 | Set-Content -Path (Join-Path $job 'result.json') -Encoding UTF8
    Write-Checkpoint 'exported' 'Native DWG + PDF exported (requires human review)'
    Write-Host "已產生草稿 DWG: $dwg"
    Write-Host "已產生草稿 PDF: $pdf"
    Write-Warning 'CAD/參照與 PDF 頁數尚需在你的 Inventor 2027 環境進行現場驗證；不得直接標記為 Released。'
} catch {
    Write-Checkpoint 'failed' ([string]$_)
    throw
} finally {
    if ($null -ne $lockStream) {$lockStream.Dispose()}
    Remove-Item -LiteralPath $lock -Force -ErrorAction SilentlyContinue
}
