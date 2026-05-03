# 醒来先看 Morning Board

当前版本：`v1.8.2`

## v1.8.2 修复

- 修复 `EXAM_DB_PATH` 未定义。
- 修复 `/exams` 页面 404。
- 修复 Exam Board 入口插入到 Telegram 卡片里的问题。
- 入口现在固定放在顶部「醒来先看」标题区。
- 考试板继续使用独立数据库 `exam_board.db`。

## 覆盖升级

覆盖：

```text
app.py
static/index.html
static/exams.html
```

数据库不要删。

覆盖后重启：

```bash
python app.py
```

打开：

```text
http://100.97.142.99:5001/
http://100.97.142.99:5001/exams
```
