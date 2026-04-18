# 公开链接（GitHub Pages）— 20 人卡片预览

**卡片网页文件**：仓库根目录的 **`docs/`**（与 `module_5/preview/` 内容一致，已随 `main` 推送）。

**访问链接（启用 Pages 后）：**

- 二十人卡片：**`https://m-ny.github.io/mvp/`**
- 深色 Run Log 展开条：**`https://m-ny.github.io/mvp/runlog/`**

---

## 推荐：用 `/docs` 发布（无需 Actions、无需 PAT 的 `workflow` 权限）

仓库里已有 **`docs/index.html`** 等静态文件，你只需要在网页上点几下：

1. 打开 **`https://github.com/m-ny/mvp`** → **Settings** → **Pages**  
2. **Build and deployment** → **Source** 选 **Deploy from a branch**  
3. **Branch** 选 **`main`**，文件夹选 **`/docs`** → **Save**  
4. 等约 1 分钟，再打开：**`https://m-ny.github.io/mvp/`**

若 **Settings → Pages** 里出现 **Visit site**，点它即可。

---

## 更新二十人数据后再公开

在本地改好 `module_5/preview/` 后同步到 `docs/` 并推送：

```bash
cp module_5/preview/index.html module_5/preview/preview.css module_5/preview/preview.js module_5/preview/preview_data.json docs/
git add docs && git commit -m "chore: refresh Pages preview data" && git push
```

---

## 备选：用 GitHub Actions 发布 `module_5/preview`（需 `workflow` 权限 push 工作流）

若你更想直接从 **`module_5/preview/`** 发布、不维护 `docs/` 副本，可在 **Actions** 里自建工作流（需 PAT 勾选 **`workflow`** 才能从本机 push `.github/workflows/`）。示例 YAML 见本文件历史版本或问维护者索取。

---

**说明**：`docs/` 里的 `preview_data.json` 会随仓库公开；勿提交含真实客户隐私的数据。
