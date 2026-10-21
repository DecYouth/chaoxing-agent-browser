---
name: chaoxing-agent-browser
description: "在 Windows 上使用 agent-browser 接续超星学习通、Chaoxing 的 AI 阶梯闯关或练习页面，读取并解答题目、处理动态标签页与判分异常、结束任务并核验成绩。适用于用户要求完成若干关卡、切换账号后再做一次、接续已登录页面，尤其是要求使用 agent-browser、不要 computer-use 的场景。"
---

# 超星 Agent Browser 闯关

使用 agent-browser CLI 操作正常网页控件；不用 computer-use、CUA、坐标点击或自建 CDP 驱动。逐题读取、独立求解，再提交。此 skill 不扩大用户授权范围，也不存储账号密码、Cookie 或既往账号的固定答案。

## 1. 确定当前会话和任务

- 先检查当前工作区的进度记录与已拥有的 agent-browser 会话，接续已有工作。用户说“换了账号再做一次”时保留工作目标，但重新确认当前账号、课程、关卡和达标规则；旧成绩不能证明新账号已完成。
- 使用任务独有的命名会话。不要占用或关闭无关的 `default` 会话。本 skill 的脚本要求显式传入非 `default` 的会话名。
- 所有命令经附带的 [agent_browser.py](scripts/agent_browser.py) 调用，或直接调用已确认的 native EXE。脚本查找本机安装，不含固定用户目录，且不经过 cmd 解释参数。
- 需要 CLI 语法时，先运行 `skills get core` 读取已安装版本的指南。下列命令以当前版本支持为准；不要因文档漂移强行改用别的浏览器工具。

```powershell
# 将路径替换为当前安装的 skill 目录；会话名在本任务内保持一致。
$skillRoot = '当前 skill 的绝对目录'
$ab = Join-Path $skillRoot 'scripts\agent_browser.py'
$session = 'chaoxing-task-唯一标识'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
python $ab --session $session -- --version
python $ab --session $session -- skills get core
# 下列两条只用于已有会话；新会话先按下文用 headed 模式打开登录页。
python $ab --session $session -- tab list
python $ab --session $session -- snapshot -i
```

CLI 缺失或浏览器连接失败时，先阅读 [环境与页面故障处理](references/chaoxing-flow.md#环境与连接)。不要在每次任务中重装或升级。通过本会话拥有的可见 Chrome 让用户直接登录，等待用户确认后再继续；不要向用户索取密码或聊天中的验证码。

首次启动会话时，使用 `--headed --profile '本任务独立的 profile 绝对路径' open '用户给定 URL'`，确认当前版本参数后执行。不要先用 `tab list` 启动无界面的空会话，再期望后加 headed 参数改变已启动的浏览器。

## 2. 定位关卡

- 读取当前页面与账号证据，不凭旧的带 `enc`/`cpi` 链接判断当前身份。只在工作区本次进度记录中保存必要标识，不把认证资料写进 skill。
- 读取真实任务列表、顺序、解锁条件、已完成状态及分数要求。五关是常见实例，不把数量、题数或 85 分写死。
- 深层跨域 iframe 无法操作时，使用当前 DOM 中实际观察到的 iframe `src` 或链接打开独立标签页，并核对页面与身份。参见 [标签页与 iframe](references/chaoxing-flow.md#标签页与-iframe)。
- 点击任务卡后，下一次调用重新列出标签页、选中实际新页并读取 snapshot。新页可能异步创建，不能在同一条链中假定已跳转。

## 3. 每题的处理循环

1. 从新 snapshot 和必要的只读 `eval` 中读取本题完整题干、位宽、编码规则、选项及可用按钮。累计对话中的旧题、disabled 控件不是当前题。
2. 独立计算答案。计算题可用本地 Python 复核；固定答案位置、关键词猜测以及上一账号的答案表都不能替代阅读本题。
3. 使用当前 snapshot 中的唯一 ref 选择答案并提交。PowerShell 中 ref 必须加引号。命令失败就停下检查，不继续执行后续提交。
4. 等待当前提交按钮恢复、出现下一题，或出现结束任务/报告。每轮等待控制在 30 秒内，约 60 秒内提供一次有意义的进度更新。超时后先重新观察状态，不能重放提交。
5. 阅读反馈并记录需要复核的题目，再继续下一题。用户已授权的正常答题、换题和结束流程不需要每题另行确认。

```powershell
python $ab --session $session -- check '@e当前选项'
# 仅在选择成功、页面状态未改变时提交；ref 来自刚读取的 snapshot。
python $ab --session $session -- click '@e提交按钮'
python $ab --session $session -- snapshot -i
python $ab --session $session -- eval 'document.body.innerText.slice(-6500)'
```

`eval` 用于读取页面，不使用隐藏答案、修改分数/完成状态、构造绕过页面流程的请求。需要较长只读 JS 时使用 CLI 的 `eval --stdin`；附带包装脚本会保留标准输入。

## 4. 判分或题目异常

- 先复核自己的计算与概念，承认并修正真实作答错误。平台反馈与独立计算分开记录，不能把每次失分都归为题库错误。
- 缺选项、题干歧义或数学正确却被判错时，保存题干、全部选项、提交内容、平台反馈和复算依据。正常 UI 有“换一题”时可使用，替换题须重新求解。
- 同一异常最多尝试两次替换；若仍无法明确作答或判分持续矛盾，保留证据，继续其他独立任务，最后说明受阻项。不要无限重试、盲目反选或为追求满分重启已达标任务。
- 具体原反补码与溢出复核要点见 [计算与异常记录](references/chaoxing-flow.md#计算与异常记录)。

## 5. 结束并保存报告

完成最后一题后，AI 可能继续生成总结。等待真实可用的“结束任务”，然后按 [结束与报告状态机](references/chaoxing-flow.md#结束与报告状态机) 执行。每一步重新取 snapshot，只点击唯一确认控件。中途超时后从观察到的阶段接续，不从头重跑结束流程。

打开报告后，等待分数、知识点统计和“重新练习”都出现。附带脚本只读取已经打开的报告并截图，不答题、不结束任务、不重启练习：

```powershell
$saveReport = Join-Path $skillRoot 'scripts\save_report.py'
python $saveReport --session $session --output-prefix '工作区\outputs\本次账号别名\01-data'
```

脚本输出 `.txt`、`.png`、`.json`，不完整或分数有歧义时返回错误，不写成功记录。默认拒绝覆盖已有文件；只有确需重采集同一份报告时才加 `--overwrite`。截图仍须查看，确认报告加载完成、无遮挡，必要时重新采集。

## 6. 核验完成并交付

- 报告分数、任务卡“已完成”及分数、课程主页总体状态三方核对。总体状态可能延迟，正常刷新或等待后重新读取。
- 保存当前账号独立的进度记录：关卡标题、最终分数、报告路径、异常说明、主页状态。报告齐全但主页未达标时，不能声称全部完成。
- 截图应覆盖所有任务卡；最终以当前页面显示的已达标/完成比例/完成提示为准，不预设所有课程都有相同文案。
- 输出简洁成绩与证据链接，明确剩余阻碍或失分原因。保留用户可查看的浏览器窗口，不关闭无关页面。

更新此 skill 时仅整理可复用流程与脱敏示例，不打包浏览器 profile、Cookie、认证链接、个人成绩单或账号姓名。
