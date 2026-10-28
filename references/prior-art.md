# 现成方案与实现依据

任务核心：让候选人在自己的电脑上每天完成一次猎聘原生简历刷新，并确认实际结果。

| 来源 | 关系 | 本实现采用的部分 |
|---|---|---|
| [猎聘金卡](https://c.liepin.com/vip) 与 [特权详情](https://c.liepin.com/vip/privilege) | 官方已有自动刷新权益，属于付费方案 | 采用官方“刷新维持活跃度”的功能语义；免费网页入口另行现场核验 |
| [自动刷新简历实践](https://m.freebuf.com/articles/others-articles/182389.html) | 使用 Selenium 的历史方案，依赖 Selenium 3.11 | 采用原生按钮操作和结果核验思路；不复制历史选择器或请求接口 |
| [Selenium 官方文档](https://www.selenium.dev/documentation/) | 上述方案的浏览器执行基础 | 本机已经有浏览器控制器，复用它的登录态，无需增加 Selenium 驱动 |
| [Apple 定时任务文档](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/ScheduledJobs.html) | macOS 持久调度 | 使用用户级 `launchd` 每日调度 |
| [Windows schtasks create](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks-create) | Windows 原生调度 | 使用当前用户交互式每日任务 |

当前页面现场验证：候选人首页有免费“刷新简历”入口，稳定属性为 `data-nick="aside-vap-bottom-btn1"`。前端原生请求为 `POST https://api-c.liepin.com/api/com.liepin.cresume.refresh-resume`，参数包含 `encryResId`。这是站内接口，未发现公开候选人接口文档。普通浏览器 fetch 请求在只读 `base-property` 接口上实测返回 `flag=0`、错误码 `-1400`；仅带浏览器登录态的简单 HTTP 请求不足以复现原生调用。

裁决：复用已有浏览器控制器和操作系统调度，点击原生入口，读取网页自己发出的刷新请求结果。保留网站自己的认证和请求封装，新增账号绑定、每日去重和结果记录。没有发现可直接替代这套候选人本人端流程、并经过当前页面核验的现成开源 skill。

价值依据：[猎聘官方特权说明](https://c.liepin.com/vip/privilege) 在“自动刷新”下写明“系统在HR活跃时间自动为您刷新简历，简历排序靠前”“在HR活跃期间开启自动刷新功能,提升活跃度,让你的简历排名靠前”。这支持将持续维护活跃度、争取招聘方侧靠前展示作为项目价值；该说明描述金卡权益，没有给出免费账号的推荐门槛或确定的排序位置。

曝光率提升的幅度尚未测量；刷新完成不等于招聘方查看增加。金卡权益介绍中的频率描述也不能用于推断免费账号的额度，以账号实际页面为准。
