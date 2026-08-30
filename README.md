# Taoci Email Tailoring

一个面向中文保研、推免、考研联系导师场景的开源 Codex/Agent Skill。它把导师官网检索、证据化匹配、套磁信定制、网易邮箱草稿保存和导师追踪表同步组合成一条可复核、可断点续跑的流水线。

项目坚持两件事：不靠编造提高“匹配度”，不让个人资料进入开源仓库。

## 能做什么

- 从学院官网、教师主页和近期招生页建立候选池。
- 用学生经历标签、招生证据和来源质量对候选进行透明排序。
- 基于本地模板批量生成克制、具体、可追溯的个性化邮件。
- 连接用户自行登录的 Microsoft Edge，将邮件批量保存为网易邮箱草稿。
- 断点续跑、跳过已完成任务，避免重复草稿。
- 备份并同步 XLSX 导师追踪表，严格区分“已存草稿”和“已发送”。
- 在发布前扫描邮箱、手机号、绝对路径、会话参数和凭据痕迹。

## 快速开始

需要 Python 3.10 或更高版本。

```powershell
git clone https://github.com/<your-github-name>/taoci-email-tailoring.git
cd taoci-email-tailoring
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip setuptools
.\.venv\Scripts\python -m pip install -e .
.\.venv\Scripts\python -m taoci_email_tailoring.cli init --output private
```

编辑 `private/student_profile.json`、`private/email_template.txt` 和 `private/candidates.csv`。这些目录已被 Git 忽略。

```powershell
.\.venv\Scripts\python -m taoci_email_tailoring.cli validate-profile --profile private/student_profile.json
.\.venv\Scripts\python -m taoci_email_tailoring.cli rank --profile private/student_profile.json --candidates private/candidates.csv --output workspace/ranked_candidates.csv
.\.venv\Scripts\python -m taoci_email_tailoring.cli draft --profile private/student_profile.json --candidates workspace/ranked_candidates.csv --template private/email_template.txt --output workspace/drafts.jsonl
```

安装可选功能：

```powershell
.\.venv\Scripts\python -m pip install -e ".[xlsx,browser]"
.\.venv\Scripts\playwright install chromium
```

保存网易草稿：

```powershell
powershell -File scripts/launch_edge_cdp.ps1 -ProfileDir private/edge-profile
.\.venv\Scripts\python -m taoci_email_tailoring.netease --drafts workspace/drafts.jsonl --state workspace/netease-state.jsonl --execute
```

不加 `--execute` 只做本地预检。项目没有发送邮件的自动化实现。

## 为什么更省时间和 token

- 学生材料先压缩成带 ID 的事实库，批量写信时不必反复读取整份简历。
- 导师信息使用统一 CSV 数据合同，检索、排序、写信和追踪表共用同一份数据。
- 排序、去重、占位符替换、附件检查和状态同步由脚本完成。
- 每封草稿有稳定任务 ID；中断后只继续未完成项。
- 运行日志默认不保存正文、收件人或本地路径。

## 隐私设计

真实数据只应存在于 `private/` 和 `workspace/`。示例均为虚构内容，`.gitignore` 默认排除以下内容：

- 学生档案、简历、成绩单和模板；
- 真实导师候选表、生成邮件和追踪表；
- Edge 用户配置、截图、运行状态和日志；
- `.env`、Cookie、token 和其他凭据文件。

提交前执行：

```powershell
python -m taoci_email_tailoring.cli privacy-scan --path .
```

详细原则见 [PRIVACY.md](PRIVACY.md)。

真实批量操作中提炼出的通用经验见 [docs/LESSONS_LEARNED.md](docs/LESSONS_LEARNED.md)。

## Skill 安装

将仓库目录复制到 Codex 的 skills 目录，或保留仓库并用符号链接安装。`SKILL.md` 是技能入口，`references/` 按需加载，Python 包负责确定性工作。

## 局限

- 高校官网结构差异很大，检索阶段仍需要 Agent 浏览和人工证据判断。
- 网易邮箱 DOM 可能更新；自动化失败时会停在当前草稿并保留状态，不能把未确认操作视为成功。
- 排名只是联系优先级，不是录取概率，也不能替代对导师近期招生情况的核实。

## 开发

```powershell
python -m unittest discover -s tests -v
python -m taoci_email_tailoring.cli privacy-scan --path .
```

本项目采用 [MIT License](LICENSE)。欢迎提交适配其他邮箱、学校官网结构和追踪表格式的改进。
贡献前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。
