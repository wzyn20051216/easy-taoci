"""套磁流水线命令行入口。"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .core import (
    ValidationError,
    build_drafts,
    load_json,
    read_candidates,
    score_candidate,
    validate_profile,
    write_candidates,
    write_jsonl,
)
from .privacy import scan_path
from .workbook import sync_workbook


def _assets_dir() -> Path:
    """定位技能仓库内的虚构示例资源。"""
    path = Path(__file__).resolve().parent.parent / "assets"
    if not path.is_dir():
        raise FileNotFoundError("未找到 assets 目录；请从完整技能仓库运行 init")
    return path


def cmd_init(args: argparse.Namespace) -> int:
    """初始化被 Git 忽略的本地私有目录。"""
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    mapping = {
        "student_profile.example.json": "student_profile.json",
        "candidates.example.csv": "candidates.csv",
        "email_template.example.txt": "email_template.txt",
        "privacy-deny.example.txt": "privacy-deny.txt",
    }
    for source_name, target_name in mapping.items():
        target = output / target_name
        if target.exists() and not args.force:
            print(f"跳过已有文件：{target}")
            continue
        shutil.copy2(_assets_dir() / source_name, target)
        print(f"已创建：{target}")
    return 0


def cmd_validate_profile(args: argparse.Namespace) -> int:
    """校验学生档案。"""
    profile = load_json(Path(args.profile))
    validate_profile(profile, check_attachments=args.check_attachments)
    print(f"档案校验通过：{args.profile}")
    return 0


def cmd_rank(args: argparse.Namespace) -> int:
    """去重并按证据计算联系优先级。"""
    profile = load_json(Path(args.profile))
    validate_profile(profile)
    fieldnames, rows = read_candidates(Path(args.candidates))
    required = {"university", "college", "name", "research_tags", "email", "faculty_url", "source_checked_at"}
    missing = sorted(required - set(fieldnames))
    if missing:
        raise ValidationError(f"候选 CSV 缺少列：{','.join(missing)}")

    seen: set[tuple[str, str, str, str]] = set()
    unique_rows: list[dict[str, str]] = []
    from .core import candidate_key
    for row in rows:
        key = candidate_key(row)
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(score_candidate(row, profile))
    unique_rows.sort(key=lambda item: (-int(item["match_score"]), item.get("university", ""), item.get("name", "")))
    output_fields = list(fieldnames)
    for field in ("match_score", "match_level", "score_reasons"):
        if field not in output_fields:
            output_fields.append(field)
    write_candidates(Path(args.output), output_fields, unique_rows)
    print(f"已排序 {len(unique_rows)} 位候选：{args.output}")
    return 0


def cmd_draft(args: argparse.Namespace) -> int:
    """严格校验后批量生成 JSONL 草稿。"""
    profile = load_json(Path(args.profile))
    _, rows = read_candidates(Path(args.candidates))
    template = Path(args.template).read_text(encoding="utf-8")
    drafts = build_drafts(profile, rows, template, check_attachments=not args.allow_missing_attachments)
    write_jsonl(Path(args.output), drafts)
    print(f"已生成 {len(drafts)} 封草稿：{args.output}")
    return 0


def cmd_privacy_scan(args: argparse.Namespace) -> int:
    """扫描准备公开的目录并以退出码标记风险。"""
    root = Path(args.path).resolve()
    deny_terms = list(args.deny_term or [])
    if args.deny_file:
        deny_path = Path(args.deny_file)
        if not deny_path.is_file():
            raise FileNotFoundError(f"隐私禁词文件不存在：{deny_path}")
        deny_terms.extend(
            line.strip()
            for line in deny_path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    findings = scan_path(root, tuple(dict.fromkeys(deny_terms)))
    if not findings:
        print(f"隐私扫描通过：{root}")
        return 0
    print(f"发现 {len(findings)} 条疑似隐私：", file=sys.stderr)
    for item in findings:
        print(f"{item.path}:{item.line} [{item.kind}] {item.preview}", file=sys.stderr)
    return 2


def cmd_sync_xlsx(args: argparse.Namespace) -> int:
    """同步导师追踪表并报告备份位置。"""
    backup = sync_workbook(Path(args.workbook), Path(args.drafts), Path(args.state))
    print(f"工作簿同步完成；备份：{backup}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """构建命令行解析器。"""
    parser = argparse.ArgumentParser(description="套磁邮件定制与导师检索工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="初始化本地私有配置")
    init_parser.add_argument("--output", default="private")
    init_parser.add_argument("--force", action="store_true")
    init_parser.set_defaults(func=cmd_init)

    validate_parser = subparsers.add_parser("validate-profile", help="校验学生事实库")
    validate_parser.add_argument("--profile", required=True)
    validate_parser.add_argument("--check-attachments", action="store_true")
    validate_parser.set_defaults(func=cmd_validate_profile)

    rank_parser = subparsers.add_parser("rank", help="去重并排序导师候选")
    rank_parser.add_argument("--profile", required=True)
    rank_parser.add_argument("--candidates", required=True)
    rank_parser.add_argument("--output", required=True)
    rank_parser.set_defaults(func=cmd_rank)

    draft_parser = subparsers.add_parser("draft", help="批量生成草稿 JSONL")
    draft_parser.add_argument("--profile", required=True)
    draft_parser.add_argument("--candidates", required=True)
    draft_parser.add_argument("--template", required=True)
    draft_parser.add_argument("--output", required=True)
    draft_parser.add_argument("--allow-missing-attachments", action="store_true")
    draft_parser.set_defaults(func=cmd_draft)

    scan_parser = subparsers.add_parser("privacy-scan", help="扫描疑似隐私与凭据")
    scan_parser.add_argument("--path", default=".")
    scan_parser.add_argument("--deny-term", action="append", help="额外禁止出现的敏感片段，可重复")
    scan_parser.add_argument("--deny-file", help="每行一个敏感片段的本地文件")
    scan_parser.set_defaults(func=cmd_privacy_scan)

    xlsx_parser = subparsers.add_parser("sync-xlsx", help="同步 XLSX 导师追踪表")
    xlsx_parser.add_argument("--workbook", required=True)
    xlsx_parser.add_argument("--drafts", required=True)
    xlsx_parser.add_argument("--state", required=True)
    xlsx_parser.set_defaults(func=cmd_sync_xlsx)
    return parser


def main(argv: list[str] | None = None) -> int:
    """执行命令并把可预期错误转换为简洁提示。"""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (ValidationError, FileNotFoundError, RuntimeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
