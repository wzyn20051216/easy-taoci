"""核心数据、评分与草稿生成测试。"""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from taoci_email_tailoring.core import (
    ValidationError,
    build_drafts,
    score_candidate,
    stable_task_id,
    validate_profile,
)


def sample_profile(attachment: str = "") -> dict:
    """构造不含真实个人信息的测试档案。"""
    return {
        "student": {
            "name": "测试同学",
            "undergraduate_university": "测试大学",
            "major": "电子信息工程",
            "application_year": "2027",
        },
        "subject_template": "【{application_year}推免自荐】-{undergraduate_university}-{name}",
        "experiences": [
            {
                "id": "embedded-project",
                "title": "嵌入式项目",
                "tags": ["embedded", "iot", "sensor"],
                "evidence": "完成多传感器系统联调。",
            }
        ],
        "attachments": [attachment] if attachment else [],
    }


def sample_candidate() -> dict[str, str]:
    """构造官方示例域名候选。"""
    return {
        "university": "测试大学",
        "college": "信息学院",
        "name": "陈测试",
        "research_focus": "物联网与边缘设备",
        "research_tags": "iot;embedded",
        "email": "teacher@example.edu",
        "faculty_url": "https://faculty.example.edu/teacher",
        "source_checked_at": "2026-08-01",
        "admission_status": "confirmed",
        "match_evidence_ids": "embedded-project",
        "match_paragraph": "我关注到您在物联网与边缘设备方面的研究。结合我完成多传感器系统联调的经历，希望进一步学习相关系统设计。",
        "contact_status": "new",
    }


class CoreTests(unittest.TestCase):
    """验证可复用的确定性约束。"""

    def test_profile_rejects_duplicate_evidence_ids(self) -> None:
        profile = sample_profile()
        profile["experiences"].append(dict(profile["experiences"][0]))
        with self.assertRaises(ValidationError):
            validate_profile(profile)

    def test_score_explains_evidence_and_source(self) -> None:
        ranked = score_candidate(sample_candidate(), sample_profile(), today=date(2026, 8, 30))
        self.assertEqual("A", ranked["match_level"])
        self.assertGreaterEqual(int(ranked["match_score"]), 80)
        self.assertIn("官方来源", ranked["score_reasons"])

    def test_completed_contact_is_hard_deduplicated(self) -> None:
        candidate = sample_candidate()
        candidate["contact_status"] = "saved"
        ranked = score_candidate(candidate, sample_profile(), today=date(2026, 8, 30))
        self.assertEqual("0", ranked["match_score"])

    def test_verified_custom_official_domain_is_supported(self) -> None:
        candidate = sample_candidate()
        candidate["faculty_url"] = "https://faculty.research-example.org.cn/teacher"
        candidate["official_domains"] = "research-example.org.cn"
        ranked = score_candidate(candidate, sample_profile(), today=date(2026, 8, 30))
        self.assertIn("官方来源", ranked["score_reasons"])

    def test_build_draft_is_stable_and_uses_primary_email(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            attachment = Path(temp_dir) / "resume.pdf"
            attachment.write_bytes(b"test")
            profile = sample_profile(str(attachment))
            candidate = sample_candidate()
            candidate["email"] = "teacher@example.edu; backup@example.edu"
            template = "{{salutation}}\n\n{{match_paragraph}}\n\n{{name}}"
            first = build_drafts(profile, [candidate], template)
            second = build_drafts(profile, [candidate], template)
            self.assertEqual(first, second)
            self.assertEqual("teacher@example.edu", first[0]["recipient"])
            self.assertIn("尊敬的陈测试老师", first[0]["body"])
            self.assertEqual(candidate["match_paragraph"], first[0]["match_paragraph"])

    def test_unknown_evidence_id_blocks_draft(self) -> None:
        candidate = sample_candidate()
        candidate["match_evidence_ids"] = "invented-project"
        with self.assertRaises(ValidationError):
            build_drafts(
                sample_profile(),
                [candidate],
                "{{salutation}}\n{{match_paragraph}}",
                check_attachments=False,
            )

    def test_task_id_does_not_contain_personal_fields(self) -> None:
        candidate = sample_candidate()
        task_id = stable_task_id(candidate, "测试主题")
        self.assertRegex(task_id, r"^[0-9a-f]{24}$")
        self.assertNotIn(candidate["name"], task_id)


if __name__ == "__main__":
    unittest.main()
