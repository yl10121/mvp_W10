# GitHub Pages（`/docs`）

启用 **Settings → Pages → Branch `main` → `/docs`** 后：

| 页面 | 公开链接 |
|------|----------|
| 20 人卡片预览 | **https://m-ny.github.io/mvp/** |
| 深色 Run Log Viewer | **https://m-ny.github.io/mvp/runlog/** |

## 同步来源

- 根下 `index.html` / `preview.*` / `preview_data.json` ← **`module_5/preview/`**
- **`runlog/`** ← **`module_5/deploy/`**（`index.html`、`run_log.json`、`architecture.html`）

更新后提交示例：

```bash
cp module_5/preview/index.html module_5/preview/preview.css module_5/preview/preview.js module_5/preview/preview_data.json docs/
cp module_5/deploy/index.html docs/runlog/index.html
cp module_5/run_log.json docs/runlog/run_log.json
git add docs && git commit -m "chore: refresh Pages" && git push
```
