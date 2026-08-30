"""隐私扫描测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from easy_taoci.privacy import scan_path


class PrivacyTests(unittest.TestCase):
    """确保示例可放行、真实特征会被拦截。"""

    def test_example_email_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "example.txt").write_text("teacher@example.edu", encoding="utf-8")
            self.assertEqual([], scan_path(root))

    def test_phone_session_and_user_path_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            phone = "138" + "1234" + "5678"
            session = "sid=" + "AbCdEfGhIjKl"
            user_path = "C:" + "\\Users\\private-user\\resume.pdf"
            (root / "bad.txt").write_text(
                f"phone={phone}\nurl=https://mail.163.com/?{session}\npath={user_path}",
                encoding="utf-8",
            )
            kinds = {finding.kind for finding in scan_path(root)}
            self.assertIn("中国手机号", kinds)
            self.assertIn("邮箱会话参数", kinds)
            self.assertIn("用户目录绝对路径", kinds)

    def test_private_directory_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            private = root / "private"
            private.mkdir()
            (private / "profile.txt").write_text("138" + "1234" + "5678", encoding="utf-8")
            self.assertEqual([], scan_path(root))

    def test_custom_deny_term_checks_content_and_filename(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "private-alias-notes.txt").write_text("公开内容含 private-alias", encoding="utf-8")
            findings = scan_path(root, ("private-alias",))
            kinds = {finding.kind for finding in findings}
            self.assertIn("用户自定义禁词（文件名）", kinds)
            self.assertIn("用户自定义禁词", kinds)


if __name__ == "__main__":
    unittest.main()
