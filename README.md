# 醒来先看 Morning Board

当前版本：`v1.7.9`

## v1.7.9 更新

- 修复 Telegram 定时提醒卡片在两栏布局中溢出的问题。
- Telegram 设置区改成适合半宽卡片的分行布局：
  - 时间 + 开关
  - chat_id + bot token
  - 保存 + 测试
- 后端逻辑沿用 v1.7.8，不改数据库。

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
