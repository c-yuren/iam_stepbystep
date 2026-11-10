# Inventor Assembly Instructions Skill — v0.1.0

> **可執行的早期原型**：JSON 步驟管理及驗證已可執行，Inventor 工作副本的原生 DWG/PDF Adapter 尚需在你安裝 Inventor 2027 的 Windows PC 上驗證。它還不是完整的 IKEA 自動組裝說明書生成器。

## 需求

- Autodesk Inventor 2027、現有 `bimwright/ipt-mcp`，可正常開啟來源 `.iam`。
- Python 3.10+（純標準函式庫）用來管理計畫與驗證。
- Windows PowerShell 5.1（內建）供 Windows Inventor COM 試驗性 Adapter 使用。
- 提供可用的 Inventor 工程圖預設範本，或以 `-TemplatePath` 指定。

## 先用範例確認 CLI

```powershell
cd inventor-assembly-instructions
python scripts/assembly_cli.py init --snapshot examples/snapshot.json --job demo-job
python scripts/assembly_cli.py validate --job demo-job
python scripts/assembly_cli.py preview --job demo-job
python scripts/assembly_cli.py status --job demo-job
python -m unittest discover -s tests -v
```

`demo-job/preview-steps.svg` 只是候選步驟清單，沒有 3D 幾何，不能拿來當施工裝配指引。

## 在真實 Inventor 組立中使用

1. 啟動 Inventor 2027，開啟已保存的 `.iam`。透過 ipt-mcp 讀取 `inventor_get_document_info` 和 `inventor_get_assembly_bom`（必要時讀取約束/干涉結果）。
2. 將上面結果轉成 `schemas/snapshot.schema.json` 的 `snapshot.json`。`components[].id` 必須是**頂層** Inventor occurrence 的真實名稱，且唯一；`model_path` 使用 Windows 絕對 `.iam` 路徑。`snapshot` 的零件順序**不是**工程組裝順序。

如果暫時無法從 ipt-mcp 統一組立資料，可用內附的**唯讀** PowerShell 備援匯出當前 Inventor 組立的頂層零件（不會保存或修改原始檔）：

```powershell
powershell.exe -NoProfile -File scripts/export_snapshot.ps1 -OutFile "C:\work\snapshot.json"
```

3. 在**新的** job 目錄執行 `init`，編輯 `plan.json` 的候選步驟、合併/拆分操作與說明。`validate` 檢查每個 occurrence 出現一次。正式審核才由人員記錄 `approve`。
4. 在簡單小組立上測試 Windows Adapter。**先確定保存原始檔，且不與其他 Agent 同時寫入 Inventor。**

```powershell
powershell.exe -NoProfile -File scripts/render_inventor.ps1 -JobDir "C:\work\job-001"
# 或指定模板
powershell.exe -NoProfile -File scripts/render_inventor.ps1 -JobDir "C:\work\job-001" -TemplatePath "C:\Templates\Standard.dwg"
```

5. 產生的 `working/Assembly_WorkingCopy.iam`、`output/Assembly_Instructions.dwg` 及 `.pdf` 必須在 Inventor 2027 打開檢查：視圖、數量、全部 PDF 頁數、中文字型和參照。沒有做完就仍是 **Draft / Review Required**。
6. 若人工確認步驟：

```powershell
python scripts/assembly_cli.py approve --job "C:\work\job-001" --step S001 --reviewer "工程審核者"
python scripts/assembly_cli.py validate --job "C:\work\job-001"
```

> `approve` 僅記錄某人的人工審核聲明，不驗證其身分。**應在產圖前完成步驟確認。** `release` 有基本程式門檻，但不代表具備完整工程品質驗證。

## 安全與錯誤處理

- 首次執行會**拒絕覆寫**已存在的工作副本、DWG、PDF、`result.json`。新版本請用新 job。
- PowerShell 腳本對工作副本寫入 Design View，不寫回原始 IAM；參照零件仍可能使用原目錄，因此搬移檔案需另外用 Inventor Pack and Go。
- 在每個主要階段儲存 `checkpoint.json`，但這不等於完整的自動斷點恢復；失敗應建立新 job 或在確認安全後手動處理。
- 如果使用新的視角、爆炸圖、子組立展開或其他不支援功能，PowerShell 會**明確拒絕**，而不是默默生成錯誤文件。
- 模型 CAD 的工程合理性、實際可裝配性、工具與扭矩需要專業確認。

## 已確認產品規格

完整 Q1–Q20 參見 `references/requirements.md`。當前可運行與尚未完成的對照參見 `references/implementation-status.md`。

## 跨 Agent 共用

將本資料夾作為唯一 Git 原始來源。Codex、Claude Code、Antigravity 應使用**相同版本的 SKILL.md 與 scripts**，但 MCP 連線需各自配置。不要在不同 Agent 同時觸發 Inventor 寫入。

## IKEA 風格視覺 PDF（已可產生草稿）

除了 Inventor 原生 PDF，另有獨立的簡潔 IKEA 式版面渲染器，從**真實的組裝步驟圖片**（例如先由 `inventor_capture_view` 擷取並由人工確認的 PNG）製作 PDF；不會自己虛構 CAD 零件。

```powershell
python -m pip install reportlab
mkdir demo-job\visuals
# 將真實 CAD 步驟圖片命名為 S001.png, S002.png ... 放在 visuals 資料夾
python scripts/render_ikea_pdf.py --job demo-job --require-images
```

`--require-images` 要求每步均有實際圖片，否則報錯。拿掉此開關可建立帶「缺少 CAD 圖」佔位框的布局草稿。產物為 `output/IKEA_Layout_DRAFT.pdf`，**刻意不可當成正式的工程 PDF**。

如已確認安裝路徑，可以在各步的 `visual.arrows` 用 0–1 相對於圖片的座標提供箭頭（例：`{"from":[0.2,0.3],"to":[0.6,0.7]}`）；僅在該步經人員核准時繪製，否則拒絕。未提供可靠方向時不畫箭頭。
