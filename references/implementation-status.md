# Capability Matrix (v0.1)

| 功能 | 狀態 | 備註 |
|---|---|---|
| Skill 工作流程與 Q1–Q20 規格 | 已提供 | 文件與配置概念 |
| 讀取 Inventor 活動組立的頂層 occurrence | 唯讀 PowerShell Adapter，未實機測試 | `export_snapshot.ps1` |
| JSON snapshot→候選 steps | 已完成、測試 | 未判斷裝配順序的物理可行性 |
| `validate` 覆蓋率、重複零件、步驟審核 | 已完成、測試 | 不等於幾何驗證 |
| `approve` 具名核准紀錄 | 已完成、測試 | 不驗證審核者身分 |
| `preview` | 已完成、測試 | SVG 文字步驟清單，不是 CAD 圖 |
| Inventor COM 工作副本、Design Views、DWG/PDF | **試驗性、未實機測試** | Windows PowerShell 5.1 + Inventor 2027；僅頂層 occurrence、累積等角模式 |
| DWG 與 IAM 關聯 | 依 API 設計，待實測 | 指向工作副本 IAM；子零件仍可能指向原始目錄，搬移須 Pack and Go |
| PDF 所有 Sheet 和字型驗證 | 待實機測試 | 必須人工檢查 |
| IKEA 視覺 PDF（由真實 PNG 排版） | 已實作、待多環境驗證 | 用 ReportLab，始終標 DRAFT；方向箭頭需人工核准 |
| 自動爆炸圖、局部特寫、CAD 圖箭頭 | 未實作 | 需專用幾何與圖面註記 Adapter |
| 自動裝配路徑與工具可達性檢查 | 未實作 | 不能從組立約束直接推斷 |
| 自動 BOM Balloon、工具清單、六章節 | 未實作 | 預定能力 |
| 多來源匯入/STEP、增量更新、完整斷點續作 | 未實作 | 資料契約可擴充 |
| 跨 Agent 同步部署器 | 未實作 | 複製同一個 Skill 到各 Agent Skills 目錄即可開始 |
| Released 狀態 | CLI 包含核准 + 檔案雜湊檢查 | **沒有**模擬工程檢查證據，不應作正式工程品質認證 |

## Known limitations

- 無法在這個執行環境啟動使用者的 Inventor／ipt-mcp；沒有聲稱實機驗證。
- PowerShell Adapter 可能需要依使用者的 Inventor 範本和 COM 載入情況調整。
- 未處理元件 suppression、未解析子組立內層 occurrence；較大型或複雜的組立需先小樣本驗證。
- 不支持將 AI 自動猜測的組裝順序視為已核准的物理裝配順序。
