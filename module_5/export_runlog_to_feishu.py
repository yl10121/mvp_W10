"""
将 module_5/run_log.json 展平后写入飞书。

说明：飞书没有官方「Workspace CLI」直接向表格灌数；本脚本使用飞书开放平台 HTTP API，
用一条 Python 命令完成（效果类似 CLI）。

两种模式（FEISHU_EXPORT_MODE）:
  sheet   — 飞书「电子表格」云文档，覆盖写入某个子表（默认，最省事）
  bitable — 「多维表格」，批量新增记录（需在表中建好列名，与 runlog_export_common.HEADERS 一致）

准备:
  1) 开放平台创建企业自建应用，拿到 App ID / App Secret。
  2) 权限: bitable:app / spreadsheet 等相关读写（按控制台提示开通）。
  3) 将应用或机器人加入目标文档/多维表格为「可编辑」。

环境变量:
  FEISHU_APP_ID / FEISHU_APP_SECRET  (或 LARK_APP_ID / LARK_APP_SECRET 国际版)
  FEISHU_EXPORT_MODE=sheet | bitable

sheet 模式额外:
  FEISHU_SPREADSHEET_TOKEN  — 电子表格 URL 中 /sheets/ 后的 token
  FEISHU_SHEET_ID          — 浏览器地址栏 sheet= 后的子表 ID（如 8b342e）

bitable 模式额外:
  FEISHU_BITABLE_APP_TOKEN — 多维表格 URL 中 /base/ 后的 app_token
  FEISHU_BITABLE_TABLE_ID  — 数据表 ID（在表设置或 API 调试里可见）

用法（仓库根目录）:
  export FEISHU_APP_ID=cli_xxx
  export FEISHU_APP_SECRET=xxx
  export FEISHU_SPREADSHEET_TOKEN=xxx
  export FEISHU_SHEET_ID=xxxxxxxx
  python3 module_5/export_runlog_to_feishu.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

_M5 = Path(__file__).resolve().parent
_REPO = _M5.parent
if str(_M5) not in sys.path:
    sys.path.insert(0, str(_M5))

from runlog_export_common import HEADERS, flatten_row, load_run_log

FEISHU_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"


def _http_json(method: str, url: str, headers: dict, body: dict | None = None, timeout: int = 120) -> dict:
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {err}") from e


def _tenant_token() -> str:
    app_id = os.environ.get("FEISHU_APP_ID", "").strip() or os.environ.get("LARK_APP_ID", "").strip()
    secret = os.environ.get("FEISHU_APP_SECRET", "").strip() or os.environ.get("LARK_APP_SECRET", "").strip()
    if not app_id or not secret:
        print("请设置 FEISHU_APP_ID 与 FEISHU_APP_SECRET（或 LARK_APP_ID / LARK_APP_SECRET）。", file=sys.stderr)
        sys.exit(1)
    r = _http_json(
        "POST",
        FEISHU_TOKEN_URL,
        {"Content-Type": "application/json; charset=utf-8"},
        {"app_id": app_id, "app_secret": secret},
    )
    if r.get("code") != 0:
        print(f"获取 tenant_access_token 失败: {r}", file=sys.stderr)
        sys.exit(1)
    return str(r["tenant_access_token"])


def _col_letters(n_cols: int) -> str:
    """1-based column index n -> letter(s), e.g. 17 -> Q."""
    s = ""
    while n_cols:
        n_cols, r = divmod(n_cols - 1, 26)
        s = chr(65 + r) + s
    return s


def _export_sheet(token: str, spreadsheet_token: str, sheet_id: str, values: list[list]) -> None:
    nrows = len(values)
    ncols = len(values[0]) if values else len(HEADERS)
    end_col = _col_letters(ncols)
    range_a1 = f"{sheet_id}!A1:{end_col}{nrows}"
    url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values"
    body = {"valueRange": {"range": range_a1, "values": values}}
    r = _http_json(
        "PUT",
        url,
        {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        body,
    )
    if r.get("code") != 0:
        print(f"写入电子表格失败: {r}", file=sys.stderr)
        sys.exit(1)


def _export_bitable(token: str, app_token: str, table_id: str, rows: list[list]) -> None:
    """多维表格：批量新增记录（追加，不删旧数据）。"""
    url = (
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create"
    )
    chunk = 200
    total = 0
    for i in range(0, len(rows), chunk):
        batch = rows[i : i + chunk]
        records = []
        for row in batch:
            fields = {HEADERS[j]: row[j] for j in range(min(len(HEADERS), len(row)))}
            records.append({"fields": fields})
        r = _http_json(
            "POST",
            url,
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            {"records": records},
        )
        if r.get("code") != 0:
            print(f"写入多维表格失败: {r}", file=sys.stderr)
            sys.exit(1)
        total += len(records)
    print(f"已向多维表格新增 {total} 条记录（未删除旧记录）。")


def main() -> None:
    mode = (os.environ.get("FEISHU_EXPORT_MODE", "sheet").strip() or "sheet").lower()
    run_path = Path(
        os.environ.get("M5_RUN_LOG_PATH", "").strip() or (_REPO / "module_5" / "run_log.json")
    ).resolve()
    entries = load_run_log(run_path)
    rows = [flatten_row(e) for e in entries]
    values = [HEADERS] + rows

    token = _tenant_token()

    if mode == "bitable":
        app_token = os.environ.get("FEISHU_BITABLE_APP_TOKEN", "").strip()
        table_id = os.environ.get("FEISHU_BITABLE_TABLE_ID", "").strip()
        if not app_token or not table_id:
            print("bitable 模式请设置 FEISHU_BITABLE_APP_TOKEN 与 FEISHU_BITABLE_TABLE_ID。", file=sys.stderr)
            sys.exit(1)
        print("提示: 多维表格中请预先创建与 HEADERS 同名的文本列（见 runlog_export_common.py）。")
        _export_bitable(token, app_token, table_id, rows)
        print("完成。")
        return

    if mode != "sheet":
        print("FEISHU_EXPORT_MODE 仅支持 sheet 或 bitable。", file=sys.stderr)
        sys.exit(1)

    spreadsheet_token = os.environ.get("FEISHU_SPREADSHEET_TOKEN", "").strip()
    sheet_id = os.environ.get("FEISHU_SHEET_ID", "").strip()
    if not spreadsheet_token or not sheet_id:
        print(
            "sheet 模式请设置 FEISHU_SPREADSHEET_TOKEN（/sheets/ 后）与 FEISHU_SHEET_ID（地址栏 sheet= 后）。",
            file=sys.stderr,
        )
        sys.exit(1)

    _export_sheet(token, spreadsheet_token, sheet_id, values)
    print(f"已写入电子表格 {len(rows)} 行数据 + 表头（覆盖范围）。")
    print("在飞书中打开对应电子表格即可查看（token 与浏览器 URL 一致）。")


if __name__ == "__main__":
    main()
