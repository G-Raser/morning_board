# 醒来先看 Morning Board

一个本地运行的“猫猫开机存档板”。

它用来记录：

- 昨天/今天完成了什么
- 还没完成的 DDL
- 今天写给明天看的留言
- DDL 完成历史
- 每日提醒设置
- 亮色/暗色模式

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

如果要用手机通过 Tailscale 访问，建议把 `app.py` 最后一行从：

```python
app.run(host="127.0.0.1", port=5000, debug=True)
```

改成你的电脑 Tailscale IP：

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

## 数据备份

最重要的是备份这个文件：

```text
morning_board.db
```

这个文件包含你的任务、DDL、留言和设置。

## GitHub 注意

`.gitignore` 默认排除了：

```text
*.db
```

也就是说数据库不会被提交到仓库，避免把私人记录传上去。

如果你使用私人仓库并且确实想同步数据库，可以删除 `.gitignore` 里的 `*.db`，但一般更推荐：代码进 GitHub，数据库单独备份到网盘或硬盘。

## 目录结构

```text
morning_board/
  app.py
  requirements.txt
  README.md
  CHANGELOG.md
  .gitignore
  static/
    index.html
```

## 当前状态

当前版本可以作为 `v1.1.0` 稳定可用版：

- 支持手机填写
- 支持 SQLite 持久化
- 支持 Tailscale 访问
- 支持暗色模式启动不闪白
- 支持复制今日存档，并在剪贴板权限失败时弹出手动复制框


## v1.1.0 更新

- 修复 SQLite `CURRENT_TIMESTAMP` 显示成 UTC 时间的问题：新记录会使用电脑本地时间写入。
- DDL 新增具体时间字段，可以记录到小时和分钟。
- DDL 状态会显示更细的倒计时，例如“13小时 20分钟后”。


## v1.1.1 更新

- 修复页面刷新后“今天已完成”不显示的问题。
- 原因是复制弹窗的按钮事件绑定早于弹窗元素解析，导致 JS 初始化中断。
- 现在改为 DOMContentLoaded 后再绑定弹窗事件，页面初始 `load()` 会正常执行。
