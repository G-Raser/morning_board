# 醒来先看 Morning Board

一个本地运行的“猫猫开机存档板”，用于每天快速记录：

- 昨天/今天完成了什么
- 今天写给明天看的留言
- 每天多个小感想 / 学习碎碎念
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

## 调整 DDL 进度条刷新频率

DDL 进度条和倒计时的刷新频率在 `static/index.html` 里设置。

找到这一行：

```js
setInterval(refreshCountdowns,1000);
```

这里的 `1000` 是毫秒，也就是 1 秒。

常见设置：

```js
setInterval(refreshCountdowns,1000); // 每 1 秒更新一次，最平滑
setInterval(refreshCountdowns,3000); // 每 3 秒更新一次，比较省资源
setInterval(refreshCountdowns,5000); // 每 5 秒更新一次，更省资源
```

如果你修改了刷新间隔，建议同时调整进度条动画时间。

在 `static/index.html` 里找到：

```css
.progress-fill{
  height:100%;
  border-radius:999px;
  background:var(--accent);
  transition:width 1s linear;
  will-change:width
}
```

如果刷新间隔改成 3 秒，可以配套改成：

```css
transition:width 3s linear;
```

推荐组合：

```js
setInterval(refreshCountdowns,3000);
```

```css
transition:width 3s linear;
```

这样进度条会每 3 秒计算一次，并用 3 秒平滑滑过去，手机端会比每秒刷新更省一点。

## 当前版本

当前版本：`v1.5.1`

主要功能：

- SQLite 本地持久化
- 上板 / 下板双区域 UI
- 昨天写给今天看
- 今天写给明天看
- 按日期查看当天内容
- 每日小感想记录
- 未完成 DDL 倒计时和进度条
- DDL 到期自动归档为“过期”
- 完成 DDL 自动归档为“完成”
- 归档任务可重新启动 / 继续处理
- 未完成 DDL 可用猫猫自定义弹窗修改截止日期和时间
- 重新启动 / 继续处理任务时可用自定义弹窗选择日期和时间
- 手机端可通过 Tailscale 访问
- 每日提醒和测试提醒
- toast 轻提示
- 亮色 / 暗色模式


## v1.5.0 更新

- 新增「每日小感想」功能。
- 下板可以记录多条今天的小感想。
- 上板可以查看昨天的小感想。
- 适合记录：某个知识点很难、哪里学得很累、明天要多看什么。
- 小感想会存进 SQLite 的 `daily_thoughts` 表。

## v1.5.1 更新

- 修复 v1.5.0 中 `daily_thoughts` 表没有被创建的问题。
- `/api/state` 查询前会先确保数据库结构已初始化。
- 数据库无需手动修改，重启后会自动补表。
