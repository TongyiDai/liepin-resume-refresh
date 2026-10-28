# 浏览器绑定

绑定 JSON 是本机私有数据。通过页面 snapshot、DOM 观察和原生界面生成它；不要把示例里的说明当成可直接执行的选择器。

```json
{
  "resume_url": "https://c.liepin.com/实际观察到的简历路径",
  "identity_selector": "当前账号独有且稳定的 CSS 选择器",
  "identity_sha256": "账号锚点规范化文本的 SHA-256 小写摘要",
  "resume_id_sha256": "原生 base-property 响应 data.resId 的 SHA-256 小写摘要",
  "refresh_selector": "原生免费刷新控件的唯一 CSS 选择器",
  "refresh_text": "刷新简历",
  "status_selector": "原生刷新时间所在元素的 CSS 选择器",
  "success_selector": "刷新成功提示元素的 CSS 选择器",
  "success_text": "刷新成功",
  "success_surface_selector": null,
  "blocked_selector": null,
  "dismiss_selectors": []
}
```

`status_selector`、`success_selector`、`success_surface_selector` 和 `blocked_selector` 可以为 `null`；前三者至少有一个非空。配置成功提示时，`success_text` 必须包含“刷新”和“成功”，并与页面实际提示一致。图片形式的成功提示必须先截图确认，再绑定独有的容器选择器，不能把任意广告弹窗都当成成功。

`dismiss_selectors` 只放经过现场检查的推广弹窗关闭控件。执行器不会自动关闭验证码、账号授权或不明对话框。

身份锚点使用候选人自己的账号区域或简历所有者信息，同时核对网页原生请求返回的加密简历 ID 摘要。只匹配姓名仍不能排除同名账号。只在当前浏览器内读取响应，不导出 cookies、请求签名或明文 ID。摘要不能当成加密。

绑定时先启用 Network 事件，再导航候选人首页；读取 `/api/com.liepin.usercx.pc.user.base-property` 的原生响应 `data.resId`。该接口发生变化或响应缺失时停止，重新观察页面。刷新入口也可以位于候选人首页 `/`，使用实际页面 URL。

文本规范化算法：`textContent.replace(/\s+/g, " ").trim()`。在浏览器外用 Node 的 `createHash("sha256")` 计算摘要。只保存摘要，避免在终端打印姓名或完整简历。

要求选择器定位到一个可见元素。优先使用稳定的 `id`、`data-*`、语义属性和小范围组合；避免位置型 `nth-child`、构建生成的 class 和 snapshot ref。不要用宽泛的整个页面作为账号锚点。

执行器要求 `refresh_text` 精确等于控件的规范化文字。刷新时间只在确实指向今天时接受：本机日期、今天/今日/刚刚，或仍在当天范围内的“分钟前/小时前”。成功提示必须在点击后新出现，不能接受已有提示。

实际网页可能没有免费刷新按钮，或者电脑端入口迁移。在这种情况下报告 `binding_changed`，重新检查原生页面；不要通过编辑简历、调用旧接口或打开付费功能来凑出成功。

现场检查未完成前，绑定保持为空，定时安装命令会拒绝启用。
