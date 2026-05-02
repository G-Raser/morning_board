# 醒来先看 Morning Board

当前版本：`v1.7.0`

本地运行的猫猫开机存档板，用来记录每天完成了什么、明天要先看什么、DDL、小感想和归档。

## v1.7.0 更新

- 新增“每日切换时间”。
- 默认新的一天从 `05:00` 开始。
- 凌晨 `00:00–04:59` 仍然算前一天，适合熬夜写存档。
- 后端 `local_today_str()` 改为按每日切换时间计算，不再死按 00:00 切天。
- 前端“回到今天”和初始加载也会使用后端计算出的猫猫日期。
- 新增设置项：`day_start_hour`。

## 覆盖升级

从旧版本升级时，覆盖：

```text
app.py
static/index.html
```

数据库不用删。首次启动会自动补上设置项：

```text
day_start_hour = 5
```

## 启动

```bash
pip install -r requirements.txt
python app.py
```

浏览器打开：

```text
http://127.0.0.1:5000
```

如果用 Tailscale，把 `app.py` 最后一行改成你的 Tailscale IP 和端口。
