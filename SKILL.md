---
name: easy-taoci
description: Use this skill whenever a student asks to find or rank Chinese graduate supervisors, research official faculty pages, tailor 保研/推免/考研套磁邮件, create professor-outreach drafts, maintain a mentor tracking workbook, or batch-save drafts in NetEase 163 Mail. It covers evidence-based teacher research, honest student-to-supervisor matching, privacy-preserving local configuration, token-efficient batch generation, and verified draft-only browser automation. Never send email without the user's explicit per-batch authorization.
compatibility: Python 3.10+; optional openpyxl for XLSX and Playwright for NetEase draft automation.
---

# 套磁邮件定制与导师检索

把任务拆成可复核的流水线：`本地建档 -> 官网检索 -> 证据化排序 -> 批量定制 -> 草稿保存 -> 状态同步`。模型负责检索判断与文字表达，脚本负责格式、去重、校验、批量执行和断点续跑，以减少重复操作与 token 消耗。

## 隐私边界

1. 先创建本地私有目录，再读取学生资料。姓名、联系方式、简历、成绩单、成绩、邮件正文、真实导师名单、浏览器配置和运行日志都不得写入技能目录或 Git。
2. 使用 `assets/` 中的虚构示例初始化项目，把真实值写入被 `.gitignore` 排除的 `private/` 和 `workspace/`。
3. 不索要或记录邮箱密码、验证码、Cookie、SID、token。让用户在浏览器中自行登录。
4. 日志默认只记录不可逆任务 ID、状态和时间，不记录收件人、正文或附件路径。
5. 发布或共享前运行：

```powershell
python -m easy_taoci.cli privacy-scan --path . --deny-file private/privacy-deny.txt
```

发现疑似隐私时暂停发布，逐项确认并清理历史。
`privacy-deny.txt` 每行写一个只属于当前用户的敏感片段，如姓名、邮箱账号、旧目录名或项目代号；该文件保留在本地。

## 启动方式

在技能目录执行：

```powershell
python -m easy_taoci.cli init --output private
python -m easy_taoci.cli validate-profile --profile private/student_profile.json
```

优先复用现有用户文件；不要覆盖真实模板或追踪表。字段说明见 [references/data-contracts.md](references/data-contracts.md)。

## 第一阶段：建立事实库

把学生材料压缩成可引用证据，而不是每封邮件重复读取完整简历：

- 每段经历分配稳定 `id`，记录 `title`、`tags`、`evidence`。
- `evidence` 只写材料能够证明的事实；论文状态、排名、奖项级别和技术指标保持原意。
- 给项目打通用标签，如 `wireless`、`signal-processing`、`embedded`、`computer-vision`、`robotics`、`security`。
- 附件使用本地相对路径，默认简历和成绩单；生成草稿前检查文件存在。

完成后一次性读取结构化档案。后续批量任务只引用相关证据项，避免反复加载长文档。

## 第二阶段：导师检索

当用户给出学校和学院时，阅读 [references/teacher-research.md](references/teacher-research.md)，执行两遍检索：

1. 覆盖检索：从学院教师名录、导师目录、团队页建立尽可能完整的候选池。
2. 证据补全：逐位打开教师主页和近期招生信息，核验研究方向、邮箱、导师身份、招生状态和更新时间。

每位候选至少保留一个权威来源 URL；“正在招生”等时效性判断需要单独的近期证据。搜索摘要只用于定位，不作为最终证据。邮箱不确定就留空，不猜测地址格式。

候选表使用统一字段，并记录：

- `faculty_url`：教师或学院官方页面。
- `admission_url`、`admission_status`：近期招生证据与保守状态。
- `source_checked_at`：核验日期。
- `research_tags`：归一化方向标签。
- `match_evidence_ids`：学生事实库中可安全引用的证据 ID。
- `research_notes`：简短事实摘要，不粘贴大段网页原文。

先与已有追踪表按 `学校 + 学院 + 姓名 + 主邮箱` 去重。已发送、已存草稿或明确跳过的老师默认不重复处理。

## 第三阶段：匹配与排序

运行确定性评分，让模型把时间花在边界判断而不是手工排表：

```powershell
python -m easy_taoci.cli rank \
  --profile private/student_profile.json \
  --candidates private/candidates.csv \
  --output workspace/ranked_candidates.csv
```

评分由方向标签重合、招生证据、来源质量和邮箱可用性组成。分数用于排序，不代表录取概率。方向完全无关、缺少权威来源或已联系的候选应标记原因并降级，而不是强行个性化。

对高分候选人工复核三件事：研究方向是否仍在做、是否有近期招生迹象、学生证据是否真正相关。规则见 [references/teacher-research.md](references/teacher-research.md)。

## 第四阶段：邮件打磨

阅读 [references/writing-quality.md](references/writing-quality.md)，每封只做有价值的个性化：

1. 主题、称呼、目标方向准确。
2. 主体履历沿用用户模板，不随意重写事实。
3. 匹配段采用“老师方向 -> 学生证据 -> 下一步学习意愿”，通常 2-3 句。
4. 每个事实都能回指 `match_evidence_ids`；匹配较弱时使用克制表达。
5. 不编造课题、论文、招生意向、师生关系或“高度匹配”。

将复核后的 `match_paragraph` 写入候选 CSV，再批量生成：

```powershell
python -m easy_taoci.cli draft \
  --profile private/student_profile.json \
  --candidates workspace/ranked_candidates.csv \
  --template private/email_template.txt \
  --output workspace/drafts.jsonl
```

脚本会检查模板占位符、证据 ID、邮箱格式、重复候选、附件和空字段，并为每封草稿生成稳定任务 ID。失败项应修复后重跑；相同任务 ID 可安全断点续跑。

## 第五阶段：保存草稿

只有用户要求“写进草稿箱”时才执行浏览器自动化。先阅读 [references/netease-drafts.md](references/netease-drafts.md)。

推荐流程：

```powershell
powershell -File scripts/launch_edge_cdp.ps1 -ProfileDir private/edge-profile
# 用户在打开的 Microsoft Edge 中自行登录网易邮箱
python -m easy_taoci.netease \
  --drafts workspace/drafts.jsonl \
  --state workspace/netease-state.jsonl \
  --execute
```

关键安全规则：

- 默认不加 `--execute` 时只预检，不操作邮箱。
- 自动化代码只查找“存草稿”，不包含点击“发送”的实现。
- 每封保存前核对收件人、主题、称呼、匹配段和附件；保存后等待页面确认并记录状态。
- 只操作当前任务创建的 compose 页面；隐藏按钮不能作为可点击目标。
- 附件需同时满足“文件名可见、上传完成、无待上传提示”。
- 异常时停在当前封，保留断点；不要用坐标盲点，也不要从头重复整批。

若当前环境已有可控的登录浏览器会话，优先复用。无法连接普通 Edge 时，用脚本启动带独立本地配置的 Edge，再让用户登录；不要迁移密码或 Cookie。

## 第六阶段：同步追踪表

保存成功后再更新追踪表：

```powershell
python -m easy_taoci.cli sync-xlsx \
  --workbook private/mentor_tracker.xlsx \
  --drafts workspace/drafts.jsonl \
  --state workspace/netease-state.jsonl
```

脚本会先备份工作簿，再按稳定键 upsert。仅存草稿时 `是否已发送` 必须保持“否”；只有用户明确完成发送后才可改为“是”。更新后抽查总表和学校分表的一致性。

## 完成标准

- 每位老师的信息有权威来源和核验日期；时效性结论有近期证据。
- 每个匹配段能回指学生事实证据，没有编造。
- 草稿收件人、主题、称呼、正文与附件均通过校验。
- 浏览器状态文件显示成功，追踪表状态与实际邮箱一致。
- 没有点击发送；没有密码、会话参数或个人资料进入日志和版本库。

遇到网页验证码、站点结构变化、附件失败或状态无法确认时，报告具体阻塞并保留可恢复状态，不把“可能成功”记成成功。
