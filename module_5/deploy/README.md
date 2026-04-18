# Run Log Viewer（`index.html`）

## 为什么「打不开」或一片空白？

1. **不要只靠双击用浏览器打开 `file://…`**  
   部分浏览器对本地文件的限制不一致；若脚本报错，页面也会空白。

2. **请用本地 HTTP 打开（推荐）**  
   在本目录执行：

   ```bash
   cd module_5/deploy
   python3 -m http.server 8765
   ```

   浏览器访问：**http://127.0.0.1:8765/**

## 想看自己跑出来的最新结果？

把 **`module_5/run_log.json`** 复制到 **`module_5/deploy/run_log.json`**（与本 `index.html` 同目录）。  
页面会优先加载该文件；若没有或加载失败，则使用页面里内嵌的示例数据。

```bash
cp ../run_log.json ./run_log.json
# 然后按上面启动 http.server 再刷新页面
```
