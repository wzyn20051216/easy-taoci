"""多邮箱草稿适配器入口。"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from .core import ValidationError, read_jsonl
from .netease import validate_drafts


@dataclass(frozen=True)
class ProviderSpec:
    """描述一个邮箱草稿适配器的能力边界。"""

    key: str
    label: str
    start_url: str
    verified: bool
    notes: str


PROVIDERS: dict[str, ProviderSpec] = {
    "netease": ProviderSpec(
        key="netease",
        label="网易邮箱",
        start_url="https://mail.163.com/",
        verified=True,
        notes="已离线测试并在真实 163 邮箱草稿流程中验证。",
    ),
    "163": ProviderSpec(
        key="netease",
        label="网易 163 邮箱",
        start_url="https://mail.163.com/",
        verified=True,
        notes="网易邮箱别名，使用 netease 适配器。",
    ),
    "qq": ProviderSpec(
        key="qq",
        label="QQ 邮箱",
        start_url="https://mail.qq.com/",
        verified=False,
        notes="已纳入数据合同和启动流程；写入适配器需在用户登录页面实测选择器后启用。",
    ),
    "gmail": ProviderSpec(
        key="gmail",
        label="Gmail",
        start_url="https://mail.google.com/",
        verified=False,
        notes="已纳入数据合同和启动流程；写入适配器需在用户登录页面实测选择器后启用。",
    ),
    "outlook": ProviderSpec(
        key="outlook",
        label="Outlook 邮箱",
        start_url="https://outlook.live.com/mail/",
        verified=False,
        notes="已纳入数据合同和启动流程；写入适配器需在用户登录页面实测选择器后启用。",
    ),
}


def provider_choices() -> list[str]:
    """返回命令行可接受的 provider 名称。"""
    return sorted(PROVIDERS)


def get_provider(name: str) -> ProviderSpec:
    """解析 provider 名称，未知时给出明确错误。"""
    key = name.strip().lower()
    if key not in PROVIDERS:
        choices = "、".join(provider_choices())
        raise ValidationError(f"未知邮箱 provider：{name}；可选：{choices}")
    return PROVIDERS[key]


def default_state_path(drafts_path: Path, provider: ProviderSpec) -> Path:
    """按邮箱适配器生成默认状态文件名。"""
    return drafts_path.parent / f"{provider.key}-state.jsonl"


def _delegate_netease(args: argparse.Namespace, state_path: Path) -> int:
    """调用已验证的网易适配器，保持旧入口兼容。"""
    from . import netease

    delegated = argparse.Namespace(
        drafts=args.drafts,
        state=str(state_path),
        cdp=args.cdp,
        execute=args.execute,
        screenshots=args.screenshots,
    )
    return netease.run(delegated)


def run(args: argparse.Namespace) -> int:
    """预检或按 provider 执行草稿保存。"""
    provider = get_provider(args.provider)
    drafts_path = Path(args.drafts)
    state_path = Path(args.state) if args.state else default_state_path(drafts_path, provider)

    records = read_jsonl(drafts_path)
    validate_drafts(records)

    print(f"邮箱：{provider.label}")
    print(f"登录入口：{provider.start_url}")
    print(f"适配状态：{'已验证' if provider.verified else '待验证'}")
    print(f"状态文件：{state_path}")

    if provider.key == "netease":
        return _delegate_netease(args, state_path)

    if args.execute:
        raise RuntimeError(
            f"{provider.label} 草稿写入适配器尚未完成实测；"
            "请先让 Agent 在已登录浏览器中只读检查页面结构，再补充选择器和离线测试。"
        )

    print("预检通过。该邮箱暂未启用写入适配器，未执行任何浏览器操作。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """构建多邮箱草稿入口命令行参数。"""
    parser = argparse.ArgumentParser(description="按邮箱 provider 批量保存套磁草稿；不提供发送动作")
    parser.add_argument("--provider", required=True, choices=provider_choices(), help="邮箱 provider")
    parser.add_argument("--drafts", required=True)
    parser.add_argument("--state", help="状态文件；省略时使用 workspace/<provider>-state.jsonl")
    parser.add_argument("--cdp", default="http://127.0.0.1:9222")
    parser.add_argument("--execute", action="store_true", help="确认执行草稿箱写入；省略时仅预检")
    parser.add_argument("--screenshots", help="可选调试截图目录，文件名仅使用任务 ID")
    return parser


def main(argv: list[str] | None = None) -> int:
    """多邮箱草稿命令行入口。"""
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except (ValidationError, FileNotFoundError, RuntimeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
