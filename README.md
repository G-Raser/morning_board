# 醒来先看 Morning Board

当前版本：`v1.7.8`

## v1.7.8 更新

- 修复 Telegram 定时提醒设置区排版。
- 提醒设置拆成更稳定的两行：
  - 第一行：提醒时间、开启推送、保存、测试
  - 第二行：chat_id、bot token
- 修复页面出现横向滚动/整体看起来歪掉的问题。
- Telegram 推送后端逻辑沿用 v1.7.7。
- 保留小感想移动分类功能。

## 覆盖升级

覆盖：

```text
app.py
static/index.html
```

数据库不要删。

覆盖后重启：

```bash
python app.py
```
