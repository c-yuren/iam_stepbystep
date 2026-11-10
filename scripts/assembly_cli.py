#!/usr/bin/env python3
"""Offline, deterministic workflow manager for assembly-instructions Skill.
No Inventor connection: Inventor operations live in render_inventor.ps1.
"""
import argparse
import copy
import hashlib
import html
import json
import os
import pathlib
import sys
from datetime import datetime, timezone

VERSION = "0.1.0"
DEFAULT_SETTINGS = {
    "audience": "general", "style": "ikea", "language": "zh-TW",
    "paper": "A3", "orientation": "landscape", "layout": "adaptive",
    "export": ["dwg", "pdf"], "review_policy": "risk-tiered",
    "sections": ["cover", "parts", "tools", "before", "steps", "completion"],
}


def stamp():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def job_file(args, file_name="plan.json"):
    return pathlib.Path(args.job).resolve() / file_name


def uniq_components(comps):
    ids = [c.get("id") for c in comps]
    return all(isinstance(x, str) and x.strip() for x in ids) and len(set(ids)) == len(ids)


def evaluate(plan, job=None):
    errors, warnings = [], []
    if plan.get("schema_version") != 1:
        errors.append("schema_version 必須為 1")
    source = plan.get("source") or {}
    if not isinstance(source.get("model_path"), str) or not source["model_path"].lower().endswith(".iam"):
        errors.append("目前 Inventor DWG Adapter 僅支援有 .iam 檔案路徑的組立")
    comps = plan.get("components", [])
    steps = plan.get("steps", [])
    if not isinstance(comps, list) or not comps or not uniq_components(comps):
        errors.append("components 必須有唯一且非空的 id")
    known = {c.get("id") for c in comps if isinstance(c, dict)}
    if not steps:
        errors.append("至少需要一個組裝步驟")
    seen_ids, installed = set(), set()
    for step in steps:
        stepid = step.get("id", "(unknown)")
        if stepid in seen_ids:
            errors.append(f"重複的 Step id: {stepid}")
        seen_ids.add(stepid)
        adds = step.get("add", [])
        if not adds:
            errors.append(f"{stepid} 沒有新增零件")
        for compid in adds:
            if compid not in known:
                errors.append(f"{stepid} 使用不存在的 occurrence: {compid}")
            if compid in installed:
                errors.append(f"{compid} 被重複安裝")
            installed.add(compid)
        if not step.get("review", {}).get("approved", False):
            warnings.append(f"{stepid} 組裝順序或方向尚未人工確認")
        mode = step.get("visual", {}).get("mode", "cumulative")
        if mode != "cumulative":
            warnings.append(f"{stepid} 使用 {mode}，Inventor MVP Adapter 尚未支援")
    if known - installed:
        errors.append("有未納入步驟的 occurrence: " + ", ".join(sorted(known-installed)))
    if "steps" not in plan.get("settings", {}).get("sections", []):
        errors.append("不可移除必要的 steps 章節")
    if job is not None and (job / "result.json").exists():
        result = read_json(job / "result.json")
        if result.get("plan_sha256") != file_hash(job / "plan.json"):
            errors.append("組裝計畫於輸出後發生變更；需要重新產生成果")
        for suffix in ("dwg", "pdf"):
            entry = (result.get("artifacts") or {}).get(suffix) or {}
            target = pathlib.Path(entry.get("path", ""))
            if not target.is_file() or (entry.get("sha256") and file_hash(target) != entry["sha256"]):
                errors.append(f"{suffix.upper()} 成果不存在或 hash 不一致")
    return {"errors": errors, "warnings": warnings, "valid": not errors,
            "release_ready": not errors and not warnings}


def cmd_init(args):
    directory = pathlib.Path(args.job).resolve()
    if directory.exists() and list(directory.iterdir()):
        raise ValueError("目標工作區非空；為防止覆蓋請使用新資料夾")
    snap = read_json(args.snapshot)
    comps = snap.get("components", [])
    if not comps or not uniq_components(comps):
        raise ValueError("snapshot.components 必須包含唯一的 id；參考 examples/snapshot.json")
    path = snap.get("model_path", "")
    if not path.lower().endswith(".iam"):
        raise ValueError("第一版僅支援以 .iam 為 CAD 主模型")
    directory.mkdir(parents=True, exist_ok=True)
    steps = []
    for n, comp in enumerate(comps, start=1):
        steps.append({"id": f"S{n:03d}", "title": "安裝 " + comp.get("name", comp["id"]),
                      "add": [comp["id"]], "instructions": "裝配方向與操作要求待確認",
                      "visual": {"mode": "cumulative", "camera": "iso"},
                      "locked": False, "review": {"approved": False, "by": "", "at": None}})
    plan = {"schema_version": 1, "created_at": stamp(),
            "source": {"model_path": path, "snapshot_sha256": file_hash(args.snapshot),
                       "provenance": snap.get("provenance", "mcp-or-manual")},
            "components": comps, "steps": steps,
            "settings": copy.deepcopy(DEFAULT_SETTINGS), "document_status": "Draft",
            "limitations": ["初始步驟按輸入順序排序，不代表經驗證的工程裝配順序",
                            "預設一次安裝一個 occurrence，須由工程人員審核與合併"]}
    save_json(directory / "snapshot.json", snap)
    save_json(directory / "plan.json", plan)
    save_json(directory / "checkpoint.json", {"stage": "planned", "updated_at": stamp()})
    print(f"已建立工作區：{directory}；產生 {len(steps)} 個候選步驟（未經工程核准）")


def cmd_validate(args):
    job = pathlib.Path(args.job).resolve()
    plan = read_json(job / "plan.json")
    report = evaluate(plan, job)
    report["evaluated_at"] = stamp()
    save_json(job / "validation.json", report)
    for e in report["errors"]:
        print("ERROR:", e)
    for w in report["warnings"]:
        print("WARN:", w)
    print("Schema/Data:", "PASS" if report["valid"] else "FAIL")
    print("Release:", "READY" if report["release_ready"] else "NOT READY")
    return 0 if report["valid"] else 2


def cmd_approve(args):
    if not args.reviewer.strip():
        raise ValueError("需提供具名的審核者，不得用 AI 假冒工程審核")
    job = pathlib.Path(args.job).resolve()
    plan = read_json(job / "plan.json")
    targets = plan["steps"] if args.step == "all" else [s for s in plan["steps"] if s["id"] == args.step]
    if not targets:
        raise ValueError("找不到指定 Step")
    for step in targets:
        step["review"] = {"approved": True, "by": args.reviewer, "at": stamp(),
                          "comment": args.comment}
    plan["document_status"] = "Draft"
    save_json(job / "plan.json", plan)
    print("已記錄審核者的確認；請重新驗證與產生 DWG")


def cmd_preview(args):
    job = pathlib.Path(args.job).resolve()
    plan = read_json(job / "plan.json")
    rows = []
    for i, step in enumerate(plan["steps"]):
        y = 125 + i*130
        newparts = ", ".join(step.get("add", []))
        rows += [f'<rect x="35" y="{y-30}" width="780" height="100" rx="10" fill="white" stroke="#a2aab4"/>',
                 f'<text x="56" y="{y}" font-size="22">{html.escape(step["id"])} — {html.escape(step["title"])}</text>',
                 f'<text x="56" y="{y+34}" font-size="15" fill="#495866">新增：{html.escape(newparts)}</text>']
    height = 155 + len(plan["steps"])*130
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="850" height="{height}" viewBox="0 0 850 {height}">
<rect width="100%" height="100%" fill="#f4f5f7"/>
<text x="35" y="48" font-size="26" font-family="sans-serif">Assembly instructions · STEP PLAN</text>
<text x="35" y="78" font-size="14" fill="#a23425">僅為步驟清單預覽，不是 CAD 幾何圖、不得據此裝配</text>
<g font-family="sans-serif">{''.join(rows)}</g></svg>'''
    out = job / "preview-steps.svg"
    out.write_text(svg, encoding="utf-8")
    print("已輸出非幾何預覽：", out)


def cmd_release(args):
    job = pathlib.Path(args.job).resolve()
    plan = read_json(job / "plan.json")
    report = evaluate(plan, job)
    if not (job / "result.json").exists():
        raise ValueError("尚無 Inventor DWG/PDF 成果；不可 Released")
    if not report["release_ready"]:
        raise ValueError("未達發布條件：" + "; ".join(report["errors"] + report["warnings"]))
    if not args.reviewer:
        raise ValueError("正式發布需具名審核者")
    plan["document_status"] = "Released"
    plan["released_at"] = stamp()
    plan["released_by"] = args.reviewer
    save_json(job / "plan.json", plan)
    save_json(job / "validation.json", {**report, "evaluated_at": stamp()})
    print("已標記 Released。注意：這僅表示本流程驗收通過，不代表 CAD 全部工程要求均被自動驗證。")


def cmd_status(args):
    job = pathlib.Path(args.job).resolve()
    plan = read_json(job / "plan.json")
    print("狀態:", plan.get("document_status", "Draft"))
    print("步驟:", len(plan["steps"]))
    print("已人工核准:", sum(1 for s in plan["steps"] if s.get("review", {}).get("approved")))
    print("CAD 成果:", "存在" if (job / "result.json").exists() else "尚未產生")
    if (job / "checkpoint.json").exists():
        print("檢查點:", read_json(job / "checkpoint.json").get("stage"))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inventor Assembly Instructions workflow CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="從結構化 Inventor snapshot 建立候選組裝計畫")
    p.add_argument("--snapshot", required=True)
    p.add_argument("--job", required=True)
    p.set_defaults(fn=cmd_init)
    for name, func in [("validate", cmd_validate), ("preview", cmd_preview),
                       ("status", cmd_status), ("release", cmd_release)]:
        p = sub.add_parser(name)
        p.add_argument("--job", required=True)
        if name == "release":
            p.add_argument("--reviewer", required=True)
        p.set_defaults(fn=func)
    p = sub.add_parser("approve")
    p.add_argument("--job", required=True)
    p.add_argument("--step", required=True, help="S001 或 all")
    p.add_argument("--reviewer", required=True)
    p.add_argument("--comment", default="")
    p.set_defaults(fn=cmd_approve)
    args = parser.parse_args(argv)
    try:
        result = args.fn(args)
        return result or 0
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
