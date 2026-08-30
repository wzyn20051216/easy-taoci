"""确定性的档案校验、导师排序与草稿生成逻辑。"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)
PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")
COMPLETED_CONTACT_STATES = {"saved", "sent", "replied", "skipped"}


class ValidationError(ValueError):
    """输入数据不满足流水线约束。"""


def load_json(path: Path) -> dict[str, Any]:
    """读取 UTF-8 JSON 对象。"""
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValidationError(f"JSON 顶层必须是对象：{path}")
    return value


def validate_profile(profile: dict[str, Any], *, check_attachments: bool = False) -> list[str]:
    """校验学生事实库并返回警告列表。"""
    errors: list[str] = []
    student = profile.get("student")
    if not isinstance(student, dict):
        errors.append("缺少 student 对象")
        student = {}

    for field in ("name", "undergraduate_university", "major", "application_year"):
        if not str(student.get(field, "")).strip():
            errors.append(f"student.{field} 不能为空")

    subject_template = str(profile.get("subject_template", ""))
    if not subject_template:
        errors.append("subject_template 不能为空")
    else:
        try:
            subject_template.format_map({key: str(value) for key, value in student.items()})
        except KeyError as exc:
            errors.append(f"subject_template 使用了未知字段：{exc.args[0]}")

    experiences = profile.get("experiences")
    if not isinstance(experiences, list) or not experiences:
        errors.append("experiences 至少需要一项")
        experiences = []

    seen_ids: set[str] = set()
    for index, item in enumerate(experiences, start=1):
        if not isinstance(item, dict):
            errors.append(f"experiences[{index}] 必须是对象")
            continue
        evidence_id = str(item.get("id", "")).strip()
        if not evidence_id:
            errors.append(f"experiences[{index}].id 不能为空")
        elif evidence_id in seen_ids:
            errors.append(f"经历 ID 重复：{evidence_id}")
        else:
            seen_ids.add(evidence_id)
        if not str(item.get("evidence", "")).strip():
            errors.append(f"experiences[{index}].evidence 不能为空")
        if not normalize_tags(item.get("tags", [])):
            errors.append(f"experiences[{index}].tags 不能为空")

    attachments = profile.get("attachments", [])
    if not isinstance(attachments, list):
        errors.append("attachments 必须是数组")
    elif check_attachments:
        for raw_path in attachments:
            path = Path(str(raw_path)).expanduser()
            if not path.is_absolute():
                path = Path.cwd() / path
            if not path.is_file():
                errors.append(f"附件不存在：{raw_path}")

    if errors:
        raise ValidationError("；".join(errors))
    return []


def normalize_tags(value: Any) -> set[str]:
    """把列表或分号字符串归一化为小写标签集合。"""
    if isinstance(value, list):
        parts = value
    else:
        parts = re.split(r"[;,，、]", str(value or ""))
    return {str(part).strip().lower() for part in parts if str(part).strip()}


def profile_evidence(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """按稳定 ID 索引学生经历。"""
    return {str(item["id"]): item for item in profile["experiences"]}


def profile_tags(profile: dict[str, Any]) -> set[str]:
    """汇总学生事实库中的全部标签。"""
    tags: set[str] = set()
    for item in profile["experiences"]:
        tags.update(normalize_tags(item.get("tags", [])))
    return tags


def read_candidates(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """读取候选 CSV，并保留原始列顺序。"""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValidationError(f"候选 CSV 没有表头：{path}")
        rows = [{key: str(value or "").strip() for key, value in row.items()} for row in reader]
        return list(reader.fieldnames), rows


def write_candidates(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    """以 UTF-8 BOM 写出候选 CSV，兼容 Excel 直接打开。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def primary_email(value: str) -> str:
    """返回多个候选邮箱中的第一个有效地址。"""
    for item in re.split(r"[;,，、\s]+", value.strip()):
        if item and EMAIL_RE.match(item):
            return item
    return ""


def is_official_faculty_source(url: str) -> bool:
    """保守判断 URL 是否像高校官方来源。"""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        return False
    blocked = ("baidu.com", "bing.com", "google.com", "zhihu.com", "sohu.com")
    if any(host == domain or host.endswith("." + domain) for domain in blocked):
        return False
    return host.endswith(".edu.cn") or host.endswith(".edu") or host.endswith(".ac.cn")


def source_freshness(value: str, today: date | None = None) -> tuple[int, str]:
    """根据核验日期返回来源新鲜度分和解释。"""
    today = today or date.today()
    try:
        checked = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return 0, "缺少有效核验日期"
    age = (today - checked).days
    if age < 0:
        return 0, "核验日期位于未来"
    if age <= 180:
        return 5, "来源在 180 天内核验"
    if age <= 540:
        return 3, "来源在 18 个月内核验"
    return 0, "来源核验已超过 18 个月"


def score_candidate(row: dict[str, str], profile: dict[str, Any], today: date | None = None) -> dict[str, str]:
    """计算透明联系优先级，不把分数解释为录取概率。"""
    student_tags = profile_tags(profile)
    research_tags = normalize_tags(row.get("research_tags", ""))
    matched = sorted(student_tags & research_tags)
    denominator = max(1, min(len(research_tags), 3))
    direction_score = round(55 * min(len(matched), denominator) / denominator)

    admission = row.get("admission_status", "unknown").lower()
    admission_score = {"confirmed": 20, "likely": 12, "unknown": 4, "not_recruiting": 0}.get(admission, 4)

    official = is_official_faculty_source(row.get("faculty_url", ""))
    source_score = 10 if official else 0
    freshness_score, freshness_reason = source_freshness(row.get("source_checked_at", ""), today)
    contact_score = 10 if primary_email(row.get("email", "")) else 0

    evidence_ids = normalize_tags(row.get("match_evidence_ids", ""))
    known_ids = set(profile_evidence(profile))
    valid_evidence = sorted(evidence_ids & known_ids)

    score = direction_score + admission_score + source_score + freshness_score + contact_score
    reasons = [
        f"方向标签命中 {len(matched)} 项" + (f"：{','.join(matched)}" if matched else ""),
        f"招生状态 {admission}",
        "官方来源" if official else "来源未通过高校域名校验",
        freshness_reason,
        "有有效邮箱" if contact_score else "缺少有效邮箱",
    ]

    contact_status = row.get("contact_status", "new").lower()
    hard_reason = ""
    if contact_status in COMPLETED_CONTACT_STATES:
        score = 0
        hard_reason = f"联系状态为 {contact_status}，默认去重跳过"
    elif admission == "not_recruiting":
        score = min(score, 20)
        hard_reason = "官方信息显示当前不招生"
    elif not official:
        score = min(score, 35)
        hard_reason = "缺少可确认的官方来源"
    elif not valid_evidence:
        score = min(score, 40)
        hard_reason = "没有可回指的学生经历证据"
    if hard_reason:
        reasons.append(hard_reason)

    if score >= 80:
        level = "A"
    elif score >= 65:
        level = "B"
    elif score >= 45:
        level = "C"
    else:
        level = "D"

    updated = dict(row)
    updated["match_score"] = str(score)
    updated["match_level"] = level
    updated["score_reasons"] = "；".join(reasons)
    return updated


def candidate_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    """生成候选去重键。"""
    return (
        row.get("university", "").casefold(),
        row.get("college", "").casefold(),
        row.get("name", "").casefold(),
        primary_email(row.get("email", "")).casefold(),
    )


def validate_candidate(row: dict[str, str], profile: dict[str, Any], row_number: int) -> list[str]:
    """校验一位候选生成草稿所需的事实与字段。"""
    errors: list[str] = []
    for field in ("university", "college", "name", "research_focus", "faculty_url", "source_checked_at"):
        if not row.get(field, "").strip():
            errors.append(f"第 {row_number} 行缺少 {field}")
    if not primary_email(row.get("email", "")):
        errors.append(f"第 {row_number} 行没有有效主邮箱")
    if not is_official_faculty_source(row.get("faculty_url", "")):
        errors.append(f"第 {row_number} 行 faculty_url 不是可识别的高校官方来源")

    evidence = profile_evidence(profile)
    ids = normalize_tags(row.get("match_evidence_ids", ""))
    if not ids:
        errors.append(f"第 {row_number} 行缺少 match_evidence_ids")
    unknown = sorted(ids - set(evidence))
    if unknown:
        errors.append(f"第 {row_number} 行引用未知经历 ID：{','.join(unknown)}")
    paragraph = row.get("match_paragraph", "").strip()
    if not paragraph:
        errors.append(f"第 {row_number} 行缺少 match_paragraph")
    if "{{" in paragraph or "}}" in paragraph:
        errors.append(f"第 {row_number} 行匹配段仍有占位符")
    return errors


def render_template(template: str, values: dict[str, str]) -> str:
    """严格替换双花括号占位符，未知字段直接报错。"""
    required = {"salutation", "match_paragraph"}
    present = set(PLACEHOLDER_RE.findall(template))
    missing = required - present
    if missing:
        raise ValidationError(f"邮件模板缺少占位符：{','.join(sorted(missing))}")

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise ValidationError(f"邮件模板使用未知占位符：{key}")
        return values[key]

    rendered = PLACEHOLDER_RE.sub(replace, template).strip() + "\n"
    if "{{" in rendered or "}}" in rendered:
        raise ValidationError("邮件正文仍有未替换占位符")
    return rendered


def stable_task_id(row: dict[str, str], subject: str) -> str:
    """生成不可逆且跨重跑稳定的草稿任务 ID。"""
    raw = "\x1f".join((*candidate_key(row), subject.strip())).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def build_drafts(
    profile: dict[str, Any],
    rows: list[dict[str, str]],
    template: str,
    *,
    check_attachments: bool = True,
) -> list[dict[str, Any]]:
    """从候选表生成浏览器可消费的 JSONL 草稿记录。"""
    validate_profile(profile, check_attachments=check_attachments)
    seen: set[tuple[str, str, str, str]] = set()
    errors: list[str] = []
    drafts: list[dict[str, Any]] = []
    student = {key: str(value) for key, value in profile["student"].items()}
    subject = str(profile["subject_template"]).format_map(student)

    attachments: list[str] = []
    for raw_path in profile.get("attachments", []):
        path = Path(str(raw_path)).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        attachments.append(str(path.resolve()))

    for row_number, row in enumerate(rows, start=2):
        status = row.get("contact_status", "new").lower()
        if status in COMPLETED_CONTACT_STATES:
            continue
        key = candidate_key(row)
        if key in seen:
            errors.append(f"第 {row_number} 行候选重复：{row.get('name', '')}")
            continue
        seen.add(key)
        errors.extend(validate_candidate(row, profile, row_number))
        if errors and any(message.startswith(f"第 {row_number} 行") for message in errors):
            continue

        values = dict(student)
        values.update(
            {
                "salutation": f"尊敬的{row['name']}老师：",
                "match_paragraph": row["match_paragraph"].strip(),
                "target_university": row["university"],
                "target_college": row["college"],
                "teacher_name": row["name"],
                "research_focus": row["research_focus"],
            }
        )
        body = render_template(template, values)
        task_id = stable_task_id(row, subject)
        drafts.append(
            {
                "task_id": task_id,
                "recipient": primary_email(row["email"]),
                "subject": subject,
                "body": body,
                "match_paragraph": row["match_paragraph"].strip(),
                "attachments": attachments,
                "teacher": {
                    "university": row["university"],
                    "college": row["college"],
                    "name": row["name"],
                    "research_focus": row["research_focus"],
                    "faculty_url": row["faculty_url"],
                    "match_score": row.get("match_score", ""),
                },
            }
        )

    if errors:
        raise ValidationError("；".join(errors))
    return drafts


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    """写出 UTF-8 JSONL。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """读取 JSONL，并在错误时报告准确行号。"""
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"{path} 第 {line_number} 行不是有效 JSON：{exc}") from exc
            if not isinstance(record, dict):
                raise ValidationError(f"{path} 第 {line_number} 行必须是 JSON 对象")
            records.append(record)
    return records
