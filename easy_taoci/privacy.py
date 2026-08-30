"""面向开源发布的轻量隐私扫描器。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


TEXT_SUFFIXES = {
    ".md", ".txt", ".py", ".ps1", ".json", ".toml", ".yml", ".yaml",
    ".csv", ".ini", ".cfg", ".html", ".js", ".ts",
}
EXCLUDED_DIRS = {".git", "private", "workspace", ".venv", "venv", "__pycache__", "dist", "build"}


@dataclass(frozen=True)
class Finding:
    """一条疑似隐私发现。"""

    path: Path
    line: int
    kind: str
    preview: str


PATTERNS = {
    "非示例邮箱": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "中国手机号": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "疑似身份证号": re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)"),
    "用户目录绝对路径": re.compile(r"(?:[A-Za-z]:\\Users\\[^\\\s]+\\|/(?:Users|home)/[^/\s]+/)"),
    "邮箱会话参数": re.compile(r"(?:[?&#]|\b)(?:sid|authuser|login_hint)=[A-Z0-9._%+-]{1,}", re.IGNORECASE),
    "疑似凭据赋值": re.compile(r"\b(?:password|passwd|cookie|access[_-]?token|api[_-]?key)\s*[:=]\s*['\"]?[^\s'\"]{8,}", re.IGNORECASE),
}


def _allowed_email(value: str) -> bool:
    """允许 RFC 保留示例域名，避免示例数据产生噪声。"""
    domain = value.rsplit("@", 1)[-1].lower()
    return domain in {"example.com", "example.org", "example.net", "example.edu"} or domain.endswith(".example.edu")


def scan_path(root: Path, deny_terms: tuple[str, ...] = ()) -> list[Finding]:
    """扫描仓库文本文件中的常见隐私和会话痕迹。"""
    findings: list[Finding] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in EXCLUDED_DIRS or part.endswith(".egg-info") for part in path.relative_to(root).parts):
            continue
        relative_path = path.relative_to(root)
        for term in deny_terms:
            if term and term.casefold() in str(relative_path).casefold():
                findings.append(Finding(relative_path, 0, "用户自定义禁词（文件名）", str(relative_path)))
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            for term in deny_terms:
                if term and term.casefold() in line.casefold():
                    preview = line.strip()
                    if len(preview) > 160:
                        preview = preview[:157] + "..."
                    findings.append(Finding(relative_path, line_number, "用户自定义禁词", preview))
            for kind, pattern in PATTERNS.items():
                for match in pattern.finditer(line):
                    value = match.group(0)
                    if kind == "非示例邮箱" and _allowed_email(value):
                        continue
                    preview = line.strip()
                    if len(preview) > 160:
                        preview = preview[:157] + "..."
                    findings.append(Finding(relative_path, line_number, kind, preview))
    return findings
