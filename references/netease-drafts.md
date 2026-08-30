# 网易邮箱草稿自动化

## 为什么使用 CDP

浏览器自动化需要连接一个用户可见、由用户自行登录的 Edge 会话。普通已运行 Edge 通常没有开放调试端口，无法可靠接管；脚本会启动独立配置目录并开放本机 CDP 端口。配置目录位于 `private/`，不会进入 Git。

## 准备

```powershell
python -m pip install -e ".[browser]"
playwright install chromium
powershell -File scripts/launch_edge_cdp.ps1 -ProfileDir private/edge-profile
```

在新打开的 Edge 中自行登录 `https://mail.163.com/`。不要把密码、验证码或登录 URL 发给 Agent。

## 预检与执行

```powershell
python -m taoci_email_tailoring.netease --drafts workspace/drafts.jsonl --state workspace/netease-state.jsonl
python -m taoci_email_tailoring.netease --drafts workspace/drafts.jsonl --state workspace/netease-state.jsonl --execute
```

预检确认草稿文件、附件、任务 ID 和浏览器连接参数。执行模式只处理状态文件中尚未成功的任务。

## 已验证的网易页面特征

网易写信页可能保留隐藏的旧模块，所以选择器必须同时满足“最新/可见”，不能简单点击第一个同名按钮：

- 收件人：可见的 `input.nui-editableAddr-ipt`。
- 主题：可见的 `input[id$="_subjectInput"]`。
- 正文：`body.isContentEditable` 的最新 iframe。
- 附件：可见写信模块关联的 `input[type=file]`；隐藏 input 可以通过 Playwright 设置文件。
- 存草稿：文字等于“存草稿”且边界框宽高大于 1 的按钮。

页面结构变化时应暂停，先用只读检查更新选择器。不要退回到屏幕坐标批量点击，因为多屏、缩放和焦点变化会导致错位。

## 成功条件

保存前：

- 页面只存在当前任务的目标收件人和主题；
- 正文称呼、匹配段、附件名正确；
- 每个附件均显示完成，页面无“待上传”或“请稍候”。

保存后：

- 页面出现草稿已保存相关反馈，或写信模块切换到 draft 状态；
- 状态文件新增该任务的 `saved` 记录；
- 调试截图仅在显式 `--screenshots` 时保存，并使用任务 ID 而非姓名命名。

## 故障恢复

- 单封失败后立即停止，记录错误类型，不自动跳到下一封。
- 修复后重跑，已 `saved` 的任务会被跳过。
- 如果页面已经填好但保存按钮选择失败，先只读检查可见按钮，再重试当前任务。
- 草稿箱中出现旧半成品时，先列出并人工确认；删除是破坏性操作，不由批量保存脚本处理。

## 安全边界

项目刻意不提供发送动作，也不包含“发送”按钮选择器。即使用户要求保存草稿，仍不等于授权发送。需要发送时应单独明确范围并由用户在邮箱中复核。
