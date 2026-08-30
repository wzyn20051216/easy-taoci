"""通过用户已登录的 Microsoft Edge 批量保存网易邮箱草稿。"""

from __future__ import annotations

import argparse
import html
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .core import EMAIL_RE, ValidationError, read_jsonl


def _load_playwright():
    """延迟加载浏览器可选依赖。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("浏览器自动化需要安装：python -m pip install -e \".[browser]\"") from exc
    return sync_playwright


def validate_drafts(records: list[dict[str, Any]]) -> None:
    """在连接邮箱前完成全部本地预检。"""
    errors: list[str] = []
    seen_ids: set[str] = set()
    for index, record in enumerate(records, start=1):
        task_id = str(record.get("task_id", ""))
        if not task_id:
            errors.append(f"第 {index} 封缺少 task_id")
        elif task_id in seen_ids:
            errors.append(f"第 {index} 封 task_id 重复")
        seen_ids.add(task_id)
        if not EMAIL_RE.match(str(record.get("recipient", ""))):
            errors.append(f"第 {index} 封收件人邮箱无效")
        if not str(record.get("subject", "")).strip():
            errors.append(f"第 {index} 封主题为空")
        if not str(record.get("body", "")).strip():
            errors.append(f"第 {index} 封正文为空")
        for raw_path in record.get("attachments", []):
            if not Path(str(raw_path)).is_file():
                errors.append(f"第 {index} 封附件不存在：{Path(str(raw_path)).name}")
    if errors:
        raise ValidationError("；".join(errors))


def saved_task_ids(state_path: Path) -> set[str]:
    """读取已成功任务，支持幂等断点续跑。"""
    if not state_path.is_file():
        return set()
    return {str(item.get("task_id")) for item in read_jsonl(state_path) if item.get("status") == "saved"}


def append_state(state_path: Path, task_id: str, status: str, error_type: str = "") -> None:
    """追加最小化状态，不记录收件人、正文和路径。"""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "task_id": task_id,
        "status": status,
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    if error_type:
        record["error_type"] = error_type
    with state_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def text_to_html(text: str) -> str:
    """把纯文本正文转换为网易编辑器可接受的简单 HTML。"""
    blocks = []
    for line in text.splitlines():
        blocks.append(f"<div>{html.escape(line)}</div>" if line.strip() else "<div><br></div>")
    return "".join(blocks)


def mail_page(context: Any) -> Any:
    """定位已登录的网易邮箱主页面。"""
    pages = [page for page in context.pages if "mail.163.com" in page.url]
    if not pages:
        raise RuntimeError("未找到网易邮箱页面；请在受控 Edge 中登录后重试")
    pages.sort(key=lambda page: "js6/main.jsp" in page.url, reverse=True)
    page = pages[0]
    page.bring_to_front()
    page.wait_for_load_state("domcontentloaded", timeout=15000)
    if "mail.163.com/js6/main.jsp" not in page.url:
        raise RuntimeError("网易邮箱尚未进入登录后的主页面")
    return page


def open_new_compose(page: Any) -> None:
    """用网易自身路由打开全新的写信模块。"""
    cid = f"c:{int(time.time() * 1000)}"
    payload = quote('{"type":"compose","fullScreen":true,"cid":"' + cid + '"}')
    page.evaluate("payload => { location.hash = 'module=compose.ComposeModule|' + payload; }", payload)
    page.wait_for_timeout(1500)
    visible_locator(page.locator('input[id$="_subjectInput"]')).wait_for(timeout=15000)


def visible_locator(locator: Any) -> Any:
    """返回最后一个可见元素，规避网易残留的隐藏写信模块。"""
    for index in range(locator.count() - 1, -1, -1):
        candidate = locator.nth(index)
        if candidate.is_visible():
            return candidate
    raise RuntimeError("页面中没有找到可见的目标控件")


def newest_editor_frame(page: Any) -> Any:
    """定位最新的可编辑正文 iframe。"""
    frames = []
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        try:
            if frame.evaluate("document.body ? document.body.isContentEditable : false"):
                frames.append(frame)
        except Exception:
            continue
    if not frames:
        raise RuntimeError("没有找到正文编辑器 iframe")
    return frames[-1]


def fill_message(page: Any, draft: dict[str, Any]) -> None:
    """填写收件人、主题与正文。"""
    recipient = visible_locator(page.locator("input.nui-editableAddr-ipt"))
    recipient.click()
    recipient.fill(str(draft["recipient"]))
    page.keyboard.press("Enter")
    page.wait_for_timeout(500)

    subject = visible_locator(page.locator('input[id$="_subjectInput"]'))
    subject.fill(str(draft["subject"]))
    frame = newest_editor_frame(page)
    frame.evaluate(
        """
        htmlBody => {
            document.body.innerHTML = htmlBody;
            document.body.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: ''}));
            document.body.dispatchEvent(new Event('change', {bubbles: true}));
        }
        """,
        text_to_html(str(draft["body"])),
    )
    page.wait_for_timeout(400)


def attach_files(page: Any, paths: list[str]) -> None:
    """上传附件并同时验证文件名、完成数量和等待提示。"""
    if not paths:
        return
    upload = page.locator('input[type="file"]').last
    upload.set_input_files(paths)
    names = [Path(path).name for path in paths]
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        body_text = page.locator("body").inner_text(timeout=5000)
        names_visible = all(name in body_text for name in names)
        uploading = "待上传" in body_text or "请稍候" in body_text
        completed = body_text.count("上传完成") >= len(paths)
        if names_visible and completed and not uploading:
            return
        page.wait_for_timeout(800)
    raise RuntimeError("附件未在 60 秒内全部显示上传完成")


def verify_filled(page: Any, draft: dict[str, Any]) -> None:
    """保存前复核关键字段，防止上一封内容残留。"""
    subject = visible_locator(page.locator('input[id$="_subjectInput"]')).input_value().strip()
    if subject != str(draft["subject"]).strip():
        raise RuntimeError("主题回读不一致")
    page_text = page.locator("body").inner_text(timeout=5000)
    if str(draft["recipient"]) not in page_text:
        raise RuntimeError("收件人回读不一致")
    frame_text = newest_editor_frame(page).locator("body").inner_text().strip()
    teacher_name = str(draft.get("teacher", {}).get("name", ""))
    if teacher_name and f"尊敬的{teacher_name}老师" not in frame_text:
        raise RuntimeError("正文称呼与当前导师不一致")
    match_paragraph = str(draft.get("match_paragraph", "")).strip()
    if match_paragraph and match_paragraph not in frame_text:
        raise RuntimeError("个性化匹配段回读不一致")


def save_draft(page: Any) -> None:
    """只点击可见的“存草稿”，并等待页面确认。"""
    clicked = page.evaluate(
        """
        () => {
            const nodes = Array.from(document.querySelectorAll('div.js-component-button.nui-btn, button, [role="button"]'));
            const target = nodes.find((node) => {
                const text = (node.innerText || node.textContent || '').trim();
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return text === '存草稿' && rect.width > 1 && rect.height > 1 && style.visibility !== 'hidden';
            });
            if (!target) return false;
            target.click();
            return true;
        }
        """
    )
    if not clicked:
        raise RuntimeError("未找到可见的存草稿按钮")

    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        page.wait_for_timeout(500)
        body = page.locator("body").inner_text(timeout=5000)
        url = page.url
        confirmed_text = any(text in body for text in ("已保存到草稿箱", "保存草稿成功", "草稿保存成功"))
        draft_route = '"type":"draft"' in url or "%22type%22:%22draft%22" in url
        if confirmed_text or draft_route:
            return
    raise RuntimeError("点击存草稿后未获得明确成功反馈")


def run(args: argparse.Namespace) -> int:
    """预检或执行批量草稿保存。"""
    drafts_path = Path(args.drafts)
    state_path = Path(args.state)
    drafts = read_jsonl(drafts_path)
    validate_drafts(drafts)
    completed = saved_task_ids(state_path)
    pending = [item for item in drafts if str(item["task_id"]) not in completed]
    print(f"草稿总数：{len(drafts)}；已完成：{len(completed)}；待处理：{len(pending)}")
    if not args.execute:
        print("预检通过。未连接邮箱，未执行任何浏览器写操作。")
        return 0
    if not pending:
        print("没有待处理草稿。")
        return 0

    screenshot_dir = Path(args.screenshots) if args.screenshots else None
    if screenshot_dir:
        screenshot_dir.mkdir(parents=True, exist_ok=True)

    sync_playwright = _load_playwright()
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(args.cdp)
        if not browser.contexts:
            raise RuntimeError("CDP 浏览器没有可用上下文")
        page = mail_page(browser.contexts[0])
        for index, draft in enumerate(pending, start=1):
            task_id = str(draft["task_id"])
            try:
                open_new_compose(page)
                fill_message(page, draft)
                attach_files(page, [str(path) for path in draft.get("attachments", [])])
                verify_filled(page, draft)
                if screenshot_dir:
                    page.screenshot(path=str(screenshot_dir / f"{task_id}_before.png"), full_page=True)
                save_draft(page)
                if screenshot_dir:
                    page.screenshot(path=str(screenshot_dir / f"{task_id}_after.png"), full_page=True)
                append_state(state_path, task_id, "saved")
                print(f"[{index}/{len(pending)}] 已保存任务 {task_id}")
            except Exception as exc:
                append_state(state_path, task_id, "failed", type(exc).__name__)
                raise RuntimeError(f"任务 {task_id} 失败并已停止：{type(exc).__name__}: {exc}") from exc
    return 0


def build_parser() -> argparse.ArgumentParser:
    """构建网易草稿命令行参数。"""
    parser = argparse.ArgumentParser(description="在网易邮箱中批量保存草稿；不提供发送动作")
    parser.add_argument("--drafts", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--cdp", default="http://127.0.0.1:9222")
    parser.add_argument("--execute", action="store_true", help="确认执行草稿箱写入；省略时仅预检")
    parser.add_argument("--screenshots", help="可选调试截图目录，文件名仅使用任务 ID")
    return parser


def main(argv: list[str] | None = None) -> int:
    """网易草稿命令行入口。"""
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except (ValidationError, FileNotFoundError, RuntimeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
