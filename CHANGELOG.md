# Changelog

## v1.7.0

- 新增“每日切换时间”设置。
- 默认 `05:00` 才切换到新的一天。
- 修复午夜 00:00 后页面自动进入下一天，导致熬夜时无法继续编辑当前存档的问题。
- 后端新增 `DEFAULT_DAY_START_HOUR`、`get_day_start_hour()`。
- `/api/state` 返回 `day_start_hour`。
- `/api/settings` 支持保存 `day_start_hour`。
