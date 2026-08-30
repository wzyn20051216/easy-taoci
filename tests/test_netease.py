"""网易自动化的离线安全测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from taoci_email_tailoring.netease import append_state, saved_task_ids, text_to_html, validate_drafts


class NetEaseTests(unittest.TestCase):
    """不启动浏览器也能验证预检与断点状态。"""

    def test_html_escapes_body(self) -> None:
        rendered = text_to_html("第一行\n\n<script>alert(1)</script>")
        self.assertIn("&lt;script&gt;", rendered)
        self.assertNotIn("<script>", rendered)

    def test_state_resume_only_accepts_saved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state = Path(temp_dir) / "state.jsonl"
            append_state(state, "a" * 24, "failed", "RuntimeError")
            append_state(state, "b" * 24, "saved")
            self.assertEqual({"b" * 24}, saved_task_ids(state))
            text = state.read_text(encoding="utf-8")
            self.assertNotIn("recipient", text)
            self.assertNotIn("body", text)

    def test_missing_attachment_blocks_before_browser(self) -> None:
        records = [{
            "task_id": "a" * 24,
            "recipient": "teacher@example.edu",
            "subject": "主题",
            "body": "正文",
            "attachments": ["missing.pdf"],
        }]
        with self.assertRaises(ValueError):
            validate_drafts(records)


if __name__ == "__main__":
    unittest.main()
