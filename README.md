# Morning Board

一个本地运行的个人晨间面板，用来把「昨天做了什么」「今天先看什么」「DDL 还有多久」「考试复习到哪一步」放在同一个页面里。

项目目前是一个轻量 Flask + SQLite 小应用：后端负责保存数据和提供 API，前端使用原生 HTML/CSS/JavaScript，不需要前端构建流程。

当前版本：`v1.8.3`

## 主要功能

### 1. 晨间主页

主页地址：`/`

主页用于每天早上快速恢复状态，也可以晚上收尾时写给明天看。

支持：

- 查看昨天记录的完成事项。
- 查看昨天的小感想和气泡分组。
- 查看昨天归档的 DDL。
- 给今天记录已经完成的事情。
- 用 emoji 气泡记录今天的小感想。
- 新增、完成、修改、删除 DDL。
- 给明天写一段留言。
- 复制今日存档，方便手动备份或贴到别处。
- 切换亮色 / 暗色主题。
- 设置「新的一天从几点开始」，默认是早上 5 点。

### 2. DDL 管理

主页里可以添加 DDL，包括：

- 事项名称
- 截止日期
- 截止时间
- 备注

DDL 会按时间排序，并显示紧急程度。已完成的任务会进入当天归档；过期未完成的任务会自动归档为 expired，避免一直堆在未完成列表里吓人。

### 3. 小感想气泡

小感想不是只有一条线性列表，而是可以用 emoji 建立不同气泡。

例如：

- `📚` 复习感想
- `😵` 崩溃碎碎念
- `💡` 灵感
- `🐱` 猫猫留言

每个气泡里可以继续添加小句子，也可以把句子移动到别的 emoji 气泡里。

### 4. Telegram 定时提醒

主页底部可以设置 Telegram 提醒。

支持：

- 设置提醒时间。
- 开启 / 关闭 Telegram 推送。
- 保存 bot token 和 chat id。
- 发送测试消息。

提醒内容会在每天指定时间附近发送一次，用来提醒你写今日完成和明日留言。

### 5. Exam Board 考试复习板

考试板地址：`/exams`

Exam Board 用来单独管理考试复习，不和主页 DDL 混在一起。

支持：

- 添加课程编号和课程名。
- 设置考试时间。
- 自动显示考试倒计时。
- 记录考试地点、考试时长。
- 记录是否允许 cheat sheet。
- 写复习重点、当前进度、下一步行动。
- 为每门课添加 checklist。
- 勾选 checklist 后自动计算复习进度。
- 课程卡片可以展开 / 收起。

Exam Board 使用独立数据库 `exam_board.db`，不会污染主页的 `morning_board.db`。

## 项目结构

```text
morning_board/
├─ app.py                  # Flask 后端和 API
├─ requirements.txt         # Python 依赖
├─ run_windows.bat          # Windows 快速启动脚本
├─ run_macos_linux.sh       # macOS / Linux 快速启动脚本
├─ static/
│  ├─ index.html            # 晨间主页
│  └─ exams.html            # Exam Board 页面
├─ morning_board.db         # 主页数据库，运行后自动生成
└─ exam_board.db            # 考试板数据库，运行后自动生成
```

注意：`morning_board.db` 和 `exam_board.db` 是你的本地数据文件。升级代码时不要删除它们。

## 安装与启动

### 1. 安装 Python

建议使用 Python 3.10 或更新版本。

### 2. 安装依赖

在项目根目录执行：

```bash
pip install -r requirements.txt
```

### 3. 启动项目

直接运行：

```bash
python app.py
```

Windows 也可以双击或运行：

```bat
run_windows.bat
```

macOS / Linux 可以运行：

```bash
bash run_macos_linux.sh
```

### 4. 打开页面

默认启动地址写在 `app.py` 最底部，目前是：

```text
http://100.97.142.99:5001/
```

考试板地址是：

```text
http://100.97.142.99:5001/exams
```

如果你只想在本机访问，可以把 `app.py` 最底部的启动地址改成：

```python
app.run(host="127.0.0.1", port=5001, debug=True, use_reloader=False)
```

然后打开：

```text
http://127.0.0.1:5001/
http://127.0.0.1:5001/exams
```

## 使用方法

### 晨间主页推荐流程

早上打开主页后，可以先看：

1. 昨天完成了什么。
2. 昨天的小感想。
3. 昨晚写给今天的话。
4. 今天需要注意的 DDL。

晚上收尾时，可以写：

1. 今天完成了什么。
2. 今天有什么小感想。
3. 明天醒来第一眼应该看什么。
4. 有没有新的 DDL 要加。

这个项目的设计目标不是做复杂任务管理，而是降低每天重新启动的成本。

### 添加 DDL

在「新增 DDL」区域填写：

- 事项
- 截止日期
- 截止时间
- 备注

然后点击「添加」。

如果只知道日期、不知道具体时间，可以只填日期。没有设置时间时，系统会默认按当天 23:59 计算。

### 完成或修改 DDL

每个未完成 DDL 卡片上有三个操作：

- 「今天完成」：归档到今天完成列表。
- 「修改 DDL」：修改截止日期和时间。
- 「彻底删除」：直接删除这条记录。

已完成或过期的 DDL 会显示在归档区，也可以重新激活。

### 写给明天的留言

在「写给明天的猫猫留言」里写一句明天醒来要看的话，然后点击保存。

第二天打开主页时，它会出现在「昨晚留给今天的话」里。

### 使用 Exam Board

打开 `/exams` 后：

1. 在「添加课程」里输入课程编号、课程名和考试时间。
2. 在课程卡片里填写考试地点、时长、cheat sheet 规则、复习重点、当前进度和下一步行动。
3. 添加 checklist，例如「看完 Week 8 PPT」「整理公式」「做 mock quiz」。
4. 勾选完成项，页面会自动显示复习进度。

考试时间选择器使用和主页一致的自定义日历按钮样式，暗色模式下也能正常看清。

## 数据说明

项目使用两个 SQLite 数据库：

```text
morning_board.db
exam_board.db
```

其中：

- `morning_board.db` 保存主页数据，包括完成事项、小感想、DDL、明日留言、设置和 Telegram 配置。
- `exam_board.db` 保存考试复习板数据，包括课程信息和 checklist。

这两个文件会在第一次运行时自动创建。

如果要备份，直接复制这两个 `.db` 文件即可。

## 升级方式

升级时通常只需要覆盖代码文件：

```text
app.py
static/index.html
static/exams.html
requirements.txt
```

不要删除：

```text
morning_board.db
exam_board.db
```

覆盖后重新运行：

```bash
python app.py
```

## 常见问题

### 1. 页面打不开

先确认终端里 Flask 是否已经启动成功。

如果你不是通过 Tailscale / 局域网访问，`100.97.142.99` 可能打不开。可以把 `app.py` 最底部的 host 改成 `127.0.0.1`，然后访问：

```text
http://127.0.0.1:5001/
```

### 2. `/exams` 打不开

确认你运行的是包含 Exam Board 路由的新版 `app.py`。

如果旧版本还在运行，先停止终端里的旧服务，再重新运行：

```bash
python app.py
```

### 3. 数据不见了

先检查项目目录里是否还有：

```text
morning_board.db
exam_board.db
```

如果从不同目录启动旧版本，数据库可能生成到别的位置。`v1.8.3` 已经把数据库路径固定到 `app.py` 所在目录，避免这个问题。

### 4. Telegram 测试失败

检查：

- bot token 是否正确。
- chat id 是否正确。
- 机器是否能联网访问 Telegram API。
- 是否已经给 bot 发过消息。

保存设置后，可以先点击「测试 Telegram」确认能否收到测试消息。

### 5. 日期切换不符合我的作息

主页底部可以设置「新的一天从几点开始」。

默认是早上 5 点，也就是说凌晨 0 点到 4:59 仍然算作前一天，比较适合晚睡场景。

## 开发说明

后端主要 API 包括：

- `GET /api/state`：获取主页状态。
- `POST /api/done`：新增完成事项。
- `POST /api/tasks`：新增 DDL。
- `POST /api/notes`：保存明日留言。
- `GET /api/exams`：获取考试课程列表。
- `POST /api/exams`：新增考试课程。
- `PATCH /api/exams/<course_id>`：更新课程详情。
- `POST /api/exams/<course_id>/checklist`：新增复习 checklist。

前端没有构建工具，直接修改 `static/index.html` 或 `static/exams.html` 后刷新页面即可。

## 版本记录

### v1.8.3

- 固定 `exam_board.db` 路径到项目根目录。
- Exam Board 的考试时间选择按钮改为复用主页同款自定义 picker 样式。
- 重写 README，补充项目介绍和使用方法。

### v1.8.2

- 修复 `EXAM_DB_PATH` 未定义。
- 修复 `/exams` 页面 404。
- 修复 Exam Board 首页入口位置错误。
- Exam Board 使用独立数据库 `exam_board.db`。
