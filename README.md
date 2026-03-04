# FishClaw — 闲鱼AI助手
<p align="center">
    <img src="assets/logo.png" alt="FishClaw Logo" width="150" height="150">
</p>

闲鱼智能体，目标：微信上发一句话管理商品，在别人的帖子下评论，增加曝光等等, 持续开发中~；

## 安装

```bash
uv venv
venv\Scripts\activate
uv sync
playwright install chromium
```

## 已完成功能

### ✅ 发帖 Agent (`post_item_agent`)
- 自动发布闲置商品
- 修改商品描述
- 修改商品价格

## 待办 (TODO)

- [ ] 页面游览 Agent — 自动浏览闲鱼页面，增加账号活跃度
- [ ] 自动评论 Agent — 在他人帖子下自动评论，增加曝光
- [ ] 自动擦亮闲置 — 定时擦亮商品，提升排名
- [ ] 每日任务 Agent — 自动完成每日签到及任务