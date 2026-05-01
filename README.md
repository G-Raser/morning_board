# 醒来先看 Morning Board

一个本地运行的“猫猫开机存档板”，用于每天快速记录：

- 昨天/今天完成了什么
- 今天写给明天看的留言
- 还没完成的 DDL
- 已完成 / 已过期 DDL 归档
- 每日提醒
- 亮色 / 暗色模式

数据保存在本地 SQLite 数据库里，默认文件名是：

```text
morning_board.db
```

## 快速启动

```bash
pip install -r requirements.txt
python app.py
```

然后打开：

```text
http://127.0.0.1:5000
```

## 手机访问 / Tailscale

如果要用手机通过 Tailscale 访问，建议把 `app.py` 最后一行改成你的电脑 Tailscale IP，例如：

```python
app.run(host="100.xx.yy.zz", port=5000, debug=False)
```

然后手机打开：

```text
http://电脑名.tailfd85c0.ts.net:5000
```

或：

```text
http://100.xx.yy.zz:5000
```

测试版可以使用另一个端口，例如：

```python
app.run(host="100.xx.yy.zz", port=5001, debug=False)
```

## 正式版 / 测试版建议

推荐把正式使用和测试分开：

```text
morning_board_prod/
  app.py
  static/index.html
  morning_board.db

morning_board_test/
  app.py
  static/index.html
  morning_board.db
```

两个数据库可以同名，只要在不同文件夹里就是不同文件。

推荐流程：

```text
1. 在 test 里测试功能和造假数据
2. 测试通过后，把 app.py / static/index.html 更新到 prod
3. 正式数据只保存在 prod 的 morning_board.db
4. 每次大改前备份 prod 的 morning_board.db
```

## 数据备份

最重要的是备份：

```text
morning_board.db
```

这个文件包含你的完成记录、DDL、归档和设置。

## GitHub 注意

`.gitignore` 默认排除了：

```text
*.db
```

也就是说数据库不会被提交到仓库，避免把私人记录或测试脏数据传上去。

## 当前版本

当前版本：`v1.3.8`

主要功能：

- SQLite 本地持久化
- 上板 / 下板双区域 UI
- 昨天写给今天看
- 今天写给明天看
- 按日期查看当天内容
- 未完成 DDL 倒计时和进度条
- DDL 到期自动归档为“过期”
- 完成 DDL 自动归档为“完成”
- 归档任务可重新启动 / 继续处理
- 未完成 DDL 可修改截止日期和时间
- 手机端可通过 Tailscale 访问
- 每日提醒和测试提醒
- toast 轻提示
- 亮色 / 暗色模式
