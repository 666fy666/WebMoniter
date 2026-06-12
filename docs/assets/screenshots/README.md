# 截图目录

构建文档站时，`.github/workflows/docs.yml` 会将 `src/webUI/static/*.png`、`src/webUI/static/*.jpg` 同步到此目录。

若本地预览时图片缺失，可将截图放入 `src/webUI/static/` 目录（如 `配置管理.png` 等），或直接放入本目录后执行 `uv run mkdocs serve` 预览。
