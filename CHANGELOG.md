# Changelog

## v1.10

- Morning Board DDL 新增手动分类：`生活相关` / `学习相关`。
- 新增 DDL 时可以选择类别，修改 DDL 时也可以调整类别。
- 未完成 DDL 和已归档 DDL 会显示类别标签，并使用贴合卡片边框的柔和彩色描边区分：生活相关偏蓝色，学习相关偏紫色。
- Telegram 晚间提醒和跨天转点报告中的明日 DDL 会按类别分组显示。
- 数据库 `tasks` 表新增 `category` 字段；旧 DDL 会默认归为 `生活相关`，可在页面里再手动修改。

## v1.9.2

- 统一 Exam Board 返回 Morning Board 按钮的 hover 动效，使其与首页“去 Exam Board 看复习进度”入口保持一致。
- 返回按钮增加轻微阴影、上浮和深色模式边框细节。

## v1.9.1

- 优化 Exam Board 截图预览弹窗样式，改成更贴近图片本体的沉浸式预览。
- 关闭按钮和文件名改为浮动控件，减少标题栏和空白区域对图片预览的干扰。
- 保持与现有深色/浅色主题变量一致。

## v1.9
- Exam Board 截图支持在当前页面弹窗预览，点击遮罩 / 关闭按钮 / Esc 可关闭，不再新开页面。
- 新增 Telegram 跨天转点报告，触发时间跟“每日切换时间”一致，适合把凌晨 5 点等自定义时间作为一天分界。
- 跨天转点报告模板独立为 `telegram_rollover_report_templates.txt`，晚间提醒继续使用 `telegram_message_templates.txt`。
- Telegram 模板解析规则收紧：只有单独一整行的 `[with_done]`、`[without_done]`、`[ddl_section]`、`[rollover_with_done]`、`[rollover_without_done]`、`[rollover_ddl_section]` 等标签会被识别，注释里的标签不会生效。
- Telegram 设置区新增跨天转点报告开关和测试发送按钮。

## v1.8.17
- Telegram 晚间提醒模板支持 `{{tomorrow_ddl_section}}`。
- 明天没有 DDL 时，整段 DDL 提醒会自动隐藏，不再显示“暂时没有 DDL”。


## v1.8.16

- Telegram 晚间提醒改为外部模板文件 `telegram_message_templates.txt`，方便直接编辑文案。
- 新增两套模板：`[with_done]` 用于今天有完成记录，`[without_done]` 用于今天没有完成记录。
- 支持 `{{date}}`、`{{today_done}}`、`{{tomorrow_ddl}}` 占位符。


## v1.8.13

- Telegram 晚间提醒增加日期标题。
- Telegram 晚间提醒会附带今天已记录/完成的事项。
- 保留 v1.8.12 的明天 DDL 截止提醒。

## v1.8.8

- 将 Exam Board 保存提示 toast 调整为和主页一致的屏幕中间下方样式。

# Changelog

## v1.9.1

- 优化 Exam Board 截图预览弹窗样式，改成更贴近图片本体的沉浸式预览。
- 关闭按钮和文件名改为浮动控件，减少标题栏和空白区域对图片预览的干扰。
- 保持与现有深色/浅色主题变量一致。

## v1.8.9

- Exam Board: 日期/时间选择按钮支持再次点击收起原生选择器。


## v1.8.4

- Exam Board 支持每门课上传多张考试要求截图。
- 支持在课程详情中直接 Ctrl+V / Cmd+V 粘贴截图。
- 截图会显示缩略图，点击可打开原图。
- 支持删除单张截图。
- 删除课程时会同时删除对应截图记录和本地截图文件。
- 新增 `exam_images` 表，用来保存截图索引。
- 截图文件保存在 `static/uploads/exam_evidence/`。
- `exam_board.db` 固定到项目根目录。
- Exam Board 的考试时间选择按钮统一使用首页同款 📅 按钮样式。

## v1.8.3

- 修复 Exam Board 考试时间按钮在深色模式下看不清的问题。
- 统一考试时间选择按钮和首页日期 / 时间按钮样式。

## v1.8.2

- 修复 `EXAM_DB_PATH` 未定义。
- 修复 `/exams` 页面 404。
- 修复 Exam Board 入口位置。
- Exam Board 使用独立数据库 `exam_board.db`。
