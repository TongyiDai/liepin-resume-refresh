# 浏览器兼容

刷新判断与浏览器连接分离。两种连接方式共用同一 `browser_worker.mjs`，因此账号摘要核对、简历 ID 核对、点击前记账和成功判定一致。

| 浏览器 | 连接方式 | 验证范围 |
|---|---|---|
| Ego Lite | `ego-browser nodejs` | 已在当前 macOS 环境完成真实账号现场刷新和执行器检查 |
| Chrome / Edge / Chromium | 本机 CDP 端口 | 已提供适配器和离线协议测试；切换后须在目标浏览器实测登录与刷新 |
| Firefox / Safari | 尚无适配器 | 需要新增对应驱动，不能直接宣称兼容 |

## Ego

默认选择。使用本人首次登录的专用任务空间，配置 `--space-id <空间ID>`；每次复用同一 Page，不创建新空间，不在每日运行后结束该持续任务空间。现场测试发现新空间不能假设共享登录态。

这个空间服务于持续的每日任务。用户接管空间或关闭会话时停止执行，提示恢复登录；不能自动夺回用户控制权。永久删除每日任务后，由 Agent 按浏览器 skill 结束该空间。

## Chrome / Edge

CDP 模式需要 Node.js 22 或以上，以及用户明确配置的本机调试端口。执行器只连接 `127.0.0.1`、`localhost` 或 `::1`；不会启动浏览器或改动用户日常使用的浏览器配置。

Chrome 的新版本要求调试模式使用单独的数据目录。由用户选择并启动浏览器，使用 `--remote-debugging-port=9222 --user-data-dir=<专用目录>`，然后在该浏览器中登录猎聘。不要复用或复制日常浏览器的 cookies。参考 [Chrome 官方说明](https://developer.chrome.com/blog/remote-debugging-port) 和 [CDP](https://chromedevtools.github.io/devtools-protocol/)。

确认该浏览器中的目标候选人后生成自己的绑定，再运行：

```bash
python3 scripts/refresh.py configure --binding-file <私有绑定文件> --browser cdp --cdp-endpoint http://127.0.0.1:9222
python3 scripts/refresh.py run --dry-run
python3 scripts/refresh.py run
python3 scripts/refresh.py schedule install --time 09:03
```

配置切换会暂停原来的自动任务。先核验新浏览器，再恢复。执行器通过 CDP 新建自己的标签页，完成后关闭该标签页，保留浏览器本身和用户原有页面。

CDP 端口和浏览器要在定时触发时可用。需要无调试端口的 Chrome/Edge 集成时，可以进一步实现扩展连接器；本包不包含未经验证的浏览器扩展，也不会自动修改用户的浏览器设置。
