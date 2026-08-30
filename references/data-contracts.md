# 数据合同

## student_profile.json

```json
{
  "student": {
    "name": "学生姓名",
    "undergraduate_university": "本科院校",
    "major": "本科专业",
    "application_year": "2027"
  },
  "subject_template": "【{application_year}推免自荐】-...-{name}",
  "experiences": [
    {
      "id": "稳定且唯一的英文 ID",
      "title": "经历名称",
      "tags": ["embedded", "iot"],
      "evidence": "材料能够直接证明的一句话"
    }
  ],
  "attachments": ["./private/resume.pdf", "./private/transcript.pdf"]
}
```

`subject_template` 可使用 `name`、`undergraduate_university`、`major`、`application_year`。经历 ID 一旦用于候选表就不要随意修改。

## candidates.csv

必需列：

| 字段 | 含义 |
| --- | --- |
| university | 目标学校 |
| college | 学院 |
| name | 导师姓名 |
| research_focus | 经官网核验的研究方向摘要 |
| research_tags | 用 `;` 分隔的归一化标签 |
| email | 官网邮箱；多个邮箱用 `;`，第一个为主邮箱 |
| faculty_url | 教师或学院官方页面 |
| source_checked_at | `YYYY-MM-DD` 核验日期 |
| match_evidence_ids | 用 `;` 分隔的学生经历 ID |
| match_paragraph | 2-3 句个性化匹配段 |

推荐列：`title`、`team`、`admission_url`、`admission_status`、`research_notes`、`contact_status`。

`admission_status` 建议值：`confirmed`、`likely`、`unknown`、`not_recruiting`。只有近期官方材料明确表述时使用 `confirmed`。

`contact_status` 建议值：`new`、`drafted`、`saved`、`sent`、`replied`、`skipped`。

脚本新增列：`match_score`、`match_level`、`score_reasons`、`task_id`。不要手工把排序分数解释为录取概率。

## drafts.jsonl

每行一封草稿：

```json
{
  "task_id": "不可逆稳定哈希",
  "recipient": "teacher@example.edu",
  "subject": "邮件主题",
  "body": "纯文本正文",
  "match_paragraph": "经证据约束的个性化匹配段",
  "attachments": ["本地路径"],
  "teacher": {"university": "...", "college": "...", "name": "..."}
}
```

该文件包含个人信息，必须存放在 `workspace/`，不得提交。

## state.jsonl

每行记录一次结果：

```json
{"task_id":"...","status":"saved","timestamp":"..."}
```

允许状态：`saved`、`failed`。失败记录可包含简短 `error_type`，不写正文、收件人和本地路径。
