> “Civilization advances by extending the number of important operations which we can perform without thinking about them.”
> — Alfred North Whitehead, [An Introduction to Mathematics, Chapter V](https://introtologic.info/AboutLogicsite/whitehead%20Good%20Notation.html), 1911

<h1 align="center">猎聘简历自动刷新</h1>

<p align="center">
  <img src="https://img.shields.io/badge/Agent%20Skill-liepin--resume--refresh-2F6BFF" alt="Agent Skill">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-3fb950" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/Python-%3E%3D3.9-3572A5" alt="Python 3.9 or newer">
  <a href="https://github.com/TongyiDai/liepin-resume-refresh/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TongyiDai/liepin-resume-refresh/ci.yml?branch=main&label=CI" alt="CI status"></a>
</p>

<p align="center">持续维护简历活跃度，争取 HR 侧靠前展示；频繁刷新交给 AI。</p>

候选人频繁刷新猎聘简历，是为了持续维护活跃度，争取招聘方侧更靠前的展示和被 HR 发现的机会。猎聘官方将自动刷新与“提升活跃度”“简历排名靠前”直接联系起来。因此，刷新需要持续维护，容易变成每天都要记得、反复执行的一件事。

`liepin-resume-refresh` 把这件事交给 AI 定时任务：默认每天刷新一次，核验结果并留下记录，减少忙碌或遗忘造成的漏刷。候选人把精力留给找岗位和准备面试，需要处理登录或验证码时再接手。

## 持续刷新，是在维护被 HR 看见的机会

[猎聘官方的自动刷新说明](https://c.liepin.com/vip/privilege) 写明：

> 系统在HR活跃时间自动为您刷新简历，简历排序靠前。
>
> 在HR活跃期间开启自动刷新功能,提升活跃度,让你的简历排名靠前。

这也解释了候选人为什么会反复刷新：希望让简历保持活跃，争取招聘方侧靠前展示的机会。AI 自动刷新把这个维护动作固定下来，减少依赖本人每天记住和手工执行。

上述说明描述的是金卡自动刷新权益。本 skill 使用候选人可见的免费原生入口，默认每日一次；具体额度和可执行频率以账号页面为准。官方说明没有给出“必须每天刷新才能获得推荐”的门槛，实际推荐、排序和查看量仍由猎聘决定。

## 手工刷新，麻烦在哪里

求职时已经要花精力找岗位、准备投递和应对面试。简历刷新容易被这些更紧急的事挤到后面。设个提醒能让你想起来，但提醒响了，打开网页、点击和确认仍然要自己完成。

<p align="center">
  <img src="assets/boards/manual-refresh-pain.svg?v=2" alt="为了持续维护简历活跃度，候选人需要反复刷新；手工维护容易漏刷、重复操作和难以确认结果" width="100%">
</p>

实际操作还可能被推广弹窗挡住，或者点击后出现图片形式的成功提示。页面卡一下，只凭按钮点过，很难判断这次是否成功。这些细节也需要人停下来查看。

## AI 到点替你做完，并确认结果

第一次，AI 核对候选人本人账号和目标简历，找到原生刷新入口，并验证一次真实结果。配置完成后，每日任务负责打开猎聘、点击刷新、检查结果和记录状态。默认本机时间 09:03，可改为自己的时间。

<p align="center">
  <img src="assets/boards/ai-refresh-solution.svg?v=2" alt="猎聘简历自动刷新：本人完成首次登录，AI 负责每日刷新、核验和记录" width="100%">
</p>

优先使用宿主的长期 AI 定时功能；没有这类功能时，用 macOS 或 Windows 的本机持久调度。两种方式共用同一套记录，每个自然日最多派发一次刷新点击，已完成或暂停时跳过。

成功需要网页自己发出的刷新请求返回成功、出现新的明确提示，或原生刷新时间发生变化。登录过期、账号变化、验证码、付费要求或页面改版时停止；点击结果不明确时保留当天记录，等待本人核对。

## 对候选人的价值

主价值是持续维护简历活跃度，争取在 HR 侧更靠前展示和被发现的机会。自动执行让这件事更少依赖候选人每天记住；核验与记录则让维护是否完成可以查看。任务平时保持安静，新的异常需要本人处理时才提醒。

<p align="center">
  <img src="assets/boards/resume-maintenance-value.svg?v=2" alt="候选人价值：维护简历活跃度、争取HR侧靠前展示，并将频繁手工刷新交给AI" width="100%">
</p>

| 手工维护的问题 | Skill 如何处理 | 候选人得到什么 |
|---|---|---|
| 希望通过刷新维护活跃度，忙时却容易漏刷 | 固定时间执行并核验 | 让简历活跃度的日常维护更连续 |
| 想争取招聘方侧更靠前的展示机会 | 持续执行原生刷新动作 | 减少漏刷，持续争取招聘方侧的展示机会 |
| 打开网页、找入口、点刷新反复发生 | AI 代做日常操作 | 少一遍频繁维护，把精力留给求职 |
| 今天刷没刷、点了算不算成功，靠记忆和看提示 | 核验结果，记录日期与状态 | 完成情况可以查看，不靠猜 |
| 登录失效或页面变化，任务可能做不下去 | 停止并提示本人处理新的异常 | 平时不必盯，异常时再接手 |

自动刷新能帮助按计划完成维护；本项目尚未测量实际曝光量、招聘方查看量或面试机会的提升幅度。

## 安装与使用

安装到支持 Agent Skills 的工具中：

```bash
npx skills add TongyiDai/liepin-resume-refresh
```

也可以下载 [Release 安装包](https://github.com/TongyiDai/liepin-resume-refresh/releases)，解压后将 `liepin-resume-refresh` 文件夹放进自己的 Agent skill 目录，例如 `~/.agents/skills/`。需要 Python 3.9+ 和可连接的电脑浏览器。

对 AI 说：

```text
用 $liepin-resume-refresh 设置猎聘简历自动刷新，
每天上午 9 点左右维护简历活跃度。
```

第一次由本人输入密码、扫码或短信验证码。AI 会检查免费刷新入口、绑定本人账号和目标简历，并验证一次真实结果；完成后才启用每日任务。

之后可以继续说“查看猎聘刷新状态”“暂停自动刷新”“改到每天 10 点”“删除每日刷新任务”。切换账号或浏览器时重新验证。

完整的 [AI 每日提示词与注册步骤](references/agent-schedule.md) 和 [本机调度说明](references/scheduling.md) 均随 skill 提供。宿主必须能连接候选人自己的电脑；纯云端任务不能直接使用另一台电脑的浏览器登录态。

它只处理刷新状态；简历正文、求职状态、隐私设置、投递和消息另需授权。账号配置与执行日志留在本机，不放入仓库或发布包。

## 浏览器兼容

优先复用本人可用的浏览器环境。不同连接方式使用同一套账号核对、每日去重和结果核验。

| 浏览器 | 连接方式 | 验证范围 |
|---|---|---|
| [Ego Lite](https://github.com/citrolabs/ego-lite) | `ego-browser`，持续复用首次登录的专用任务空间 | 已完成 macOS 真实刷新与后台调度验证 |
| Chrome / Edge / Chromium | 本机 CDP 端口，Node.js 22+ | 已提供适配器并通过离线协议测试；目标浏览器需现场验证 |
| Firefox / Safari | 需要新增适配器 | 本版本未支持 |

[浏览器配置说明](references/browsers.md) 包含 CDP 的连接条件。电脑需要处于已登录状态，浏览器与登录会话可用；关机期间不能保证补跑。宿主定时能力取决于所用 AI 工具，不宣称所有 Agent 都提供长期后台调度。

## 为什么保留原生刷新入口

猎聘前端使用站内 `refresh-resume` 接口，但没有找到面向候选人的公开调用文档。普通只读请求曾返回业务错误 `-1400`。本实现保留网页自己的认证和请求封装，点击免费原生入口，并观察网页原生请求的结果。

## 验证与演示

```bash
python3 scripts/test_refresh.py
python3 scripts/demo.py
```

测试覆盖账号变化、同日去重、暂停、点击中断、陈旧成功提示、调度切换与 CDP 连接协议。CI 在 Python 3.9 和 3.13，以及 macOS、Windows、Linux 的夹具环境中运行。测试不访问候选人账号，也不能替代浏览器中的现场验证。

下面是**离线演示**：浏览器结果使用模拟值，每日去重和暂停逻辑运行真实代码，不访问猎聘或创建定时任务。

<p align="center">
  <img src="assets/demo.gif" alt="离线演示：检查、首次刷新、同日跳过与暂停" width="100%">
</p>

演示可用 [VHS](https://github.com/charmbracelet/vhs) 重建：`vhs assets/demo.tape`。设计与实现参考见 [prior-art.md](references/prior-art.md)。

## 许可

[MIT](LICENSE)。
