---
name: inventor-assembly-instructions
description: Inventor 2027 + ipt-mcp 組裝說明書製作；分析 IAM、產生候選步驟、審查、原生 DWG/PDF 草稿並驗證。支援 IKEA、Technical、Hybrid 的規劃設定。
---

# Inventor Assembly Instructions

**先確認能力，再執行。** 預設工作環境：Inventor 2027、`bimwright/ipt-mcp`。本 Skill **不授權**直接修改使用者原始 `.iam/.ipt`。所有生成操作都在新的工作區進行。

## 當任務觸發時

1. 確認使用者選擇的來源、視覺風格、讀者、輸出格式。預設 `IKEA`、一般讀者、DWG+PDF；現有多層範本與鎖定設定優先。
2. 使用 ipt-mcp 的 `inventor_health`、`inventor_get_document_info`、`inventor_get_assembly_bom`、`inventor_list_constraints`（必要時 `inventor_check_interference`）讀取當前組立。確認為 Inventor 2027 且取得實際 IAM 路徑。
3. 優先使用既有 ipt-mcp；如有必要，可執行 `scripts/export_snapshot.ps1` **唯讀備援**匯出頂層 occurrence。將讀取結果依 `schemas/snapshot.schema.json` **轉寫**為 snapshot JSON。工具回應可能因版本而不同，不得把未核實欄位假稱存在。對頂層 occurrence 用實際 `.Name`（如 `Bracket:1`）當 `id`。建立包含來源資訊與不確定項目的清單。
4. 呼叫 `python scripts/assembly_cli.py init --snapshot <snapshot> --job <new_dir>`。此命令產生**候選步驟，並非經驗證的裝配順序**。不能依原始 occurrence 排列宣稱「可實際裝配」。
5. 使用者可修改 `plan.json` 的 `steps`（順序、合併拆分、標註、模式、鎖定），並由有資格的人審核工程問題。執行 `validate`；如需記錄人工審核，使用 `approve --step S001 --reviewer "..."`。不得替使用者偽造核准。
6. 執行 `preview` 產生 **非幾何的步驟清單 SVG**。此 SVG 不是組裝圖。第一版具原生 DWG/PDF 的 Windows 試驗性 Adapter 僅支援頂層零件、累積式等角視圖；其他視圖模式須明確告知不支援，不可悄悄替換。
7. 在 Windows PowerShell 5.1、Inventor 已啟動的環境執行：`powershell -ExecutionPolicy Bypass -File scripts/render_inventor.ps1 -JobDir <new_dir>`；先在簡單測試組立驗證。Adapter 將儲存 IAM 工作副本、建立設計視圖、多 Sheet Inventor DWG 與 PDF。沒有經過 Inventor 2027 現場測試前，不得保證成功。
8. 執行 `validate` 檢查資料及檔案雜湊。針對工程正確性、箭頭、BOM、檔案參照、PDF 頁數等須由使用者在 Inventor 內審核。**正式 Released** 需要具名審核者、完整證據和可追溯檔案；不可讓 Agent 自行虛構確認。

## 必須遵守的限制

- **無真實組裝路徑資料，不自動編造路徑、扭矩、工具或安全要求。**
- 無法讀取檔案／MCP、無法驗證裝配步驟、API 失敗時，返回 `Draft` 或 `Review Required`，附明確錯誤；不假稱 Released。
- 不覆寫工作區內既有 DWG/PDF。原始 IAM 不得 Save。原始 IPT 參照不能被修改。
- `inventor_send_code` 預設停用，不能要求使用者為了便利直接開啟任意程式碼執行；優先使用現成 ipt-mcp 工具及固定參數 Adapter。
- 不同 Agent 共享同一 Skill 原始碼與版本，但 Inventor CAD 寫入不可並行。
- 逐步生成（含圖框、完整六章節、箭頭、局部放大、爆炸視圖、SVG/PNG 靜態輸出）屬已規劃功能，**不是本 MVP 已驗證的功能**。需要時清楚標示未支援並保留工作成果。

## 詳細參考

- `references/implementation-status.md`：已實作／未實作能力對照。
- `references/requirements.md`：Q1–Q20 需求承諾與版本演進。
- `references/api-sources.md`：官方 Inventor API 與 ipt-mcp 來源。
- `README.md`：Windows 安裝、執行、測試與限制。
