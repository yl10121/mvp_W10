"""
将 module_5/run_log.json 中每条记录的 output.parsed 展平后写入 Google 表格。

说明：Google 没有「写 Sheet」的官方 Workspace CLI；本脚本使用 Google Sheets API（与 gcloud 项目、
服务账号凭据配合）。步骤概要：

1) Google Cloud Console 启用「Google Sheets API」。
2) 创建服务账号，下载 JSON 密钥；把该 JSON 路径设为环境变量 GOOGLE_APPLICATION_CREDENTIALS。
3) 新建或打开一个 Google 表格，从 URL 复制 spreadsheetId（/d/<ID>/）。
4) 在表格里「共享」给服务账号邮箱（JSON 里的 client_email），权限：编辑者。
5) 设置 GOOGLE_SHEET_ID=<spreadsheetId>，然后运行本脚本。

用法（仓库根目录）:
  export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json
  export GOOGLE_SHEET_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  python3 module_5/export_runlog_to_gsheet.py

可选:
  M5_RUN_LOG_PATH — 默认 module_5/run_log.json
  GOOGLE_SHEET_TAB   — 工作表名称，默认 M5_Output（不存在则创建）
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_M5 = Path(__file__).resolve().parent
if str(_M5) not in sys.path:
    sys.path.insert(0, str(_M5))

from runlog_export_common import HEADERS, flatten_row, load_run_log


def main() -> None:
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "").strip()
    if not cred_path or not Path(cred_path).is_file():
        print("请设置 GOOGLE_APPLICATION_CREDENTIALS 为服务账号 JSON 的绝对路径。", file=sys.stderr)
        sys.exit(1)
    if not sheet_id:
        print("请设置 GOOGLE_SHEET_ID（表格 URL 中 /d/ 与 /edit 之间的字符串）。", file=sys.stderr)
        sys.exit(1)

    run_path = Path(
        os.environ.get("M5_RUN_LOG_PATH", "").strip()
        or (_REPO / "module_5" / "run_log.json")
    ).resolve()
    tab = os.environ.get("GOOGLE_SHEET_TAB", "M5_Output").strip() or "M5_Output"

    rows = [flatten_row(e) for e in load_run_log(run_path)]
    values = [HEADERS] + rows

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        print("请安装: pip install google-api-python-client google-auth", file=sys.stderr)
        sys.exit(1)

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_file(cred_path, scopes=scopes)
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)

    # 确保工作表存在
    meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    titles = {s["properties"]["title"] for s in meta.get("sheets", [])}
    if tab not in titles:
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={
                "requests": [
                    {
                        "addSheet": {
                            "properties": {"title": tab, "gridProperties": {"frozenRowCount": 1}}
                        }
                    }
                ]
            },
        ).execute()

    # 清空并写入（避免旧数据残留）
    service.spreadsheets().values().clear(
        spreadsheetId=sheet_id, range=f"'{tab}'!A:Z", body={}
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"'{tab}'!A1",
        valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()

    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
    print(f"已写入 {len(rows)} 行（含表头）到工作表「{tab}」")
    print(f"打开: {url}")


if __name__ == "__main__":
    main()
