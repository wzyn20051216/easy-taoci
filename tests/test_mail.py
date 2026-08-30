"""多邮箱草稿入口的离线安全测试。"""

from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

from easy_taoci.core import write_jsonl
from easy_taoci.mail import default_state_path, get_provider, run


class MailProviderTests(unittest.TestCase):
    """不启动浏览器也能验证 provider 路由与安全边界。"""

    def test_provider_alias_and_default_state(self) -> None:
        provider = get_provider("163")
        self.assertEqual("netease", provider.key)
        self.assertEqual(Path("workspace") / "netease-state.jsonl", default_state_path(Path("workspace/drafts.jsonl"), provider))

    def test_unverified_provider_dry_run_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            drafts = root / "drafts.jsonl"
            write_jsonl(
                drafts,
                [{
                    "task_id": "a" * 24,
                    "recipient": "teacher@example.edu",
                    "subject": "测试主题",
                    "body": "测试正文",
                    "attachments": [],
                }],
            )
            args = argparse.Namespace(
                provider="qq",
                drafts=str(drafts),
                state="",
                cdp="http://127.0.0.1:9222",
                execute=False,
                screenshots="",
            )
            self.assertEqual(0, run(args))

    def test_unverified_provider_blocks_execute(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            drafts = root / "drafts.jsonl"
            write_jsonl(
                drafts,
                [{
                    "task_id": "b" * 24,
                    "recipient": "teacher@example.edu",
                    "subject": "测试主题",
                    "body": "测试正文",
                    "attachments": [],
                }],
            )
            args = argparse.Namespace(
                provider="outlook",
                drafts=str(drafts),
                state="",
                cdp="http://127.0.0.1:9222",
                execute=True,
                screenshots="",
            )
            with self.assertRaises(RuntimeError):
                run(args)


if __name__ == "__main__":
    unittest.main()
