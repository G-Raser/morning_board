# 醒来先看 Morning Board

当前版本：`v1.7.7`

## v1.7.7 更新

- 提醒设置区改成 Telegram-only。
- 移除旧浏览器通知 UI。
- `保存提醒` 会同时保存：
  - `reminder_enabled`
  - `reminder_time`
  - `telegram_enabled`
  - `telegram_chat_id`
  - `telegram_bot_token`（留空不覆盖旧 token）
- 保留小感想移动分类功能：
  - 点开 emoji 气泡后，`↪` 可以移动小句子到别的 emoji。
- 运行地址保持：
  - `100.97.142.99:5001`

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
