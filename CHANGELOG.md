# Changelog

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
