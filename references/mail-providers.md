# 多邮箱草稿适配

`drafts.jsonl` 是邮箱无关的数据合同。浏览器适配器只负责把同一份草稿写入用户已经登录的网页邮箱草稿箱，并记录最小状态。

## Provider 状态

| Provider | 登录地址 | 写入状态 |
| --- | --- | --- |
| `netease` / `163` | `https://mail.163.com/` | 已验证 |
| `qq` | `https://mail.qq.com/` | 待登录实测 |
| `gmail` | `https://mail.google.com/` | 待登录实测 |
| `outlook` | `https://outlook.live.com/mail/` | 待登录实测 |

未验证 provider 可以做本地预检和打开登录页，但不能带 `--execute` 写入。不要为了赶进度把别的邮箱套进网易选择器。

## 通用流程

```powershell
python -m pip install -e ".[browser]"
playwright install chromium
powershell -File scripts/launch_edge_cdp.ps1 -ProfileDir private/edge-profile -Provider netease
python -m easy_taoci.mail --provider netease --drafts workspace/drafts.jsonl
python -m easy_taoci.mail --provider netease --drafts workspace/drafts.jsonl --execute
```

`--state` 可省略，默认写入 `workspace/<provider>-state.jsonl`。如果用户已经有历史状态文件，沿用原路径，避免重复草稿。

## 新增适配器要求

1. 默认 dry-run，不连接或写入邮箱。
2. `--execute` 才允许写浏览器。
3. 只保存草稿，不实现发送动作，不保存发送按钮选择器。
4. 连接用户可见、用户自行登录的浏览器，不索要密码、验证码、Cookie 或 token。
5. 每封失败立即停止，追加 `failed` 状态并保留断点。
6. 保存前回读收件人、主题、称呼、个性化匹配段和附件状态。
7. 成功状态只记录 `task_id`、`status`、`timestamp`、`provider` 和简短错误类型，不记录正文、收件人或附件路径。

## 页面实测清单

新增 QQ 邮箱、Gmail、Outlook 等适配器前，先在已登录页面只读确认：

- 写信入口是否会复用旧窗口或隐藏 compose。
- 收件人输入后是否需要 `Enter`、失焦或选择联系人气泡。
- 正文编辑器是主页面元素、iframe、shadow DOM 还是富文本组件。
- 附件上传是否有明确完成状态，文件名可见是否足够。
- 保存草稿动作是显式按钮、关闭窗口自动保存，还是快捷键触发。
- 页面是否存在广告弹窗、账号安全弹窗、语言差异或新版 UI 分支。

只有这些点都能被自动化脚本稳定验证时，才把 provider 标为已验证。
