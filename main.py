from __future__ import annotations

import re
import shutil
import argparse
import os
from datetime import datetime
from typing import List

import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt

def update_latest(run_dir: str, output_dir: str):
    """
    output/latest を最新の run_dir で上書きする
    """
    latest_dir = os.path.join(output_dir, "latest")

    # 既存 latest を消す（存在しないならOK）
    if os.path.exists(latest_dir):
        shutil.rmtree(latest_dir)

    # run_dir を丸ごとコピー
    shutil.copytree(run_dir, latest_dir)

    # どの run_dir が latest か分かるようにメモも残す（任意だけど便利）
    with open(os.path.join(output_dir, "LATEST_RUN.txt"), "w", encoding="utf-8") as f:
        f.write(os.path.basename(run_dir) + "\n")


def parse_args():
    parser = argparse.ArgumentParser(
        description="株価 → 自動レポート（price.png + summary.csv）"
    )
    parser.add_argument(
        "--tickers",
        required=True,
        help="ティッカー（カンマ区切り）例: 7203.T,6758.T,9984.T",
    )
    parser.add_argument(
        "--period",
        default="6mo",
        help="取得期間（例: 1mo, 3mo, 6mo, 1y, 2y, 5y, max）",
    )
    parser.add_argument(
        "--interval",
        default="1d",
        help="足種別（例: 1d, 1wk, 1mo）",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="出力先フォルダ（デフォルト: output）",
    )
    parser.add_argument(
    "--run-name",
    default=None,
    help="実行名（例: my_test_run）"
    )

    parser.add_argument(
    "--latest",
    action="store_true",
    help="latest フォルダを更新する"
    )
    return parser.parse_args()


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def sanitize_run_name(name: str) -> str:
    """
    フォルダ名として安全な文字だけを残す
    - 英数字
    - ハイフン
    - アンダースコア
    それ以外は _ に置換
    """
    name = name.strip()
    name = re.sub(r"[^a-zA-Z0-9_-]+", "_", name)
    name = re.sub(r"_+", "_", name)  # 連続 _ を1つに
    return name.strip("_")

def make_run_dir(base_dir: str, run_name: str | None) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if run_name:
        safe_name = sanitize_run_name(run_name)

        # 🔽 ここ！！（全部消えて空になった場合の保険）
        if not safe_name:
            safe_name = "run"

        dir_name = f"report_{ts}_{safe_name}"
    else:
        dir_name = f"report_{ts}"

    run_dir = os.path.join(base_dir, dir_name)
    os.makedirs(run_dir, exist_ok=True)
    return run_dir

def parse_tickers(raw: str) -> List[str]:
    # "7203.T, 6758.T" みたいな空白にも対応
    tickers = [t.strip() for t in raw.split(",") if t.strip()]
    # 重複排除（順序維持）
    seen = set()
    uniq = []
    for t in tickers:
        if t not in seen:
            uniq.append(t)
            seen.add(t)
    return uniq


def _normalize_yfinance_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    yfinance の download は環境/バージョンによって列が MultiIndex になることがある。
    その場合でも Open/High/Low/Close/Volume を 1段に揃える。
    """
    if isinstance(df.columns, pd.MultiIndex):
        level0 = df.columns.get_level_values(0)
        level1 = df.columns.get_level_values(1)

        if "Close" in set(level0):
            df.columns = level0
        elif "Close" in set(level1):
            df.columns = level1
        else:
            df.columns = ["_".join(map(str, c)).strip() for c in df.columns.to_list()]

    return df


def fetch_price_history(ticker: str, period: str, interval: str) -> pd.DataFrame:
    df = yf.download(
        ticker,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
    )
    if df is None or df.empty:
        raise ValueError(f"データが取得できませんでした: {ticker}")

    df = _normalize_yfinance_columns(df)
    df = df.reset_index()

    cols = [c for c in ["Date", "Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    df = df[cols].copy()

    if "Date" not in df.columns or "Close" not in df.columns:
        raise ValueError(f"取得データに Date/Close がありません: {ticker}")

    return df


def export_summary_csv(df: pd.DataFrame, ticker_dir: str, ticker: str):
    latest = df.iloc[-1]

    def _to_float(x):
        if isinstance(x, pd.Series):
            x = x.iloc[-1]
        return float(x)

    def _to_int(x):
        if isinstance(x, pd.Series):
            x = x.iloc[-1]
        return int(x)

    summary = pd.DataFrame([{
        "ticker": ticker,
        "latest_date": str(latest.get("Date", ""))[:10],
        "open": _to_float(latest["Open"]) if "Open" in df.columns else None,
        "high": _to_float(latest["High"]) if "High" in df.columns else None,
        "low": _to_float(latest["Low"]) if "Low" in df.columns else None,
        "close": _to_float(latest["Close"]) if "Close" in df.columns else None,
        "volume": _to_int(latest["Volume"]) if "Volume" in df.columns else None,
    }])

    summary_path = os.path.join(ticker_dir, "summary.csv")
    summary.to_csv(summary_path, index=False)


def export_price_png(df: pd.DataFrame, ticker_dir: str, ticker: str):
    required = {"Date", "Close"}
    if not required.issubset(df.columns):
        raise ValueError("Date / Close 列がありません。")

    x = pd.to_datetime(df["Date"], errors="coerce")
    close = pd.to_numeric(df["Close"], errors="coerce")

    tmp = pd.DataFrame({"Date": x, "Close": close}).dropna()
    if tmp.empty:
        raise ValueError("price.png 用データが空です（Date/Close を確認してください）")

    tmp["MA5"] = tmp["Close"].rolling(5).mean()
    tmp["MA25"] = tmp["Close"].rolling(25).mean()

    plt.figure(figsize=(12, 6))
    plt.plot(tmp["Date"], tmp["Close"], label="Close")
    plt.plot(tmp["Date"], tmp["MA5"], label="MA5")
    plt.plot(tmp["Date"], tmp["MA25"], label="MA25")

    plt.title(f"{ticker} Close Price (with MA)")
    plt.xlabel("Date")
    plt.ylabel("Close")
    plt.legend()
    plt.tight_layout()

    out_path = os.path.join(ticker_dir, "price.png")
    plt.savefig(out_path, dpi=200)
    plt.close()


import matplotlib.dates as mdates

def _format_volume_unit(v: float) -> tuple[float, str]:
    """
    出来高を読みやすい単位に変換（日本株想定）
    例: 12,340,000 -> 1234.0 万株
    """
    if v >= 1e8:
        return v / 1e8, "億株"
    if v >= 1e4:
        return v / 1e4, "万株"
    return v, "株"


def export_price_volume_png(df: pd.DataFrame, ticker_dir: str, ticker: str, interval: str = "1d"):
    """
    株価(終値) + 出来高を2軸で表示してPNG出力（見栄え改善版）
    """
    required = {"Date", "Close"}
    if not required.issubset(df.columns):
        raise ValueError("Date / Close 列がありません。")

    has_volume = "Volume" in df.columns

    # Date を datetime に統一
    x = pd.to_datetime(df["Date"], errors="coerce")
    close = pd.to_numeric(df["Close"], errors="coerce")

    tmp = pd.DataFrame({"Date": x, "Close": close})
    if has_volume:
        tmp["Volume"] = pd.to_numeric(df["Volume"], errors="coerce")

    tmp = tmp.dropna(subset=["Date", "Close"])
    if tmp.empty:
        raise ValueError("2軸グラフ用データが空です（Date/Close を確認してください）")

    fig, ax_price = plt.subplots(figsize=(12, 6))

    # --- 左軸：株価（線）
    ax_price.plot(tmp["Date"], tmp["Close"])
    ax_price.set_xlabel("Date")
    ax_price.set_ylabel("Close")
    ax_price.grid(True, axis="y", alpha=0.3)

    # --- 日付の潰れ対策（自動間引き + 見やすいフォーマット）
    locator = mdates.AutoDateLocator(minticks=5, maxticks=9)
    ax_price.xaxis.set_major_locator(locator)
    ax_price.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    fig.autofmt_xdate()

    # --- 右軸：出来高（棒）
    if has_volume:
        ax_vol = ax_price.twinx()

        vol_series = tmp["Volume"].fillna(0)
        v_scaled, unit = _format_volume_unit(float(vol_series.max()))
        # max 기준で単位を決めて、全部同じ単位で割る
        if unit == "億株":
            vol_plot = vol_series / 1e8
        elif unit == "万株":
            vol_plot = vol_series / 1e4
        else:
            vol_plot = vol_series

        # バー幅：データ間隔（median）から算出（1wkは太め、1dは細め）
        dates_num = mdates.date2num(tmp["Date"])
        if len(dates_num) >= 2:
            step = float(pd.Series(dates_num).diff().median())
        else:
            step = 1.0

        width = step * (0.8 if interval in ("1wk", "1w", "1mo") else 0.6)

        ax_vol.bar(tmp["Date"], vol_plot, alpha=0.25, width=width)
        ax_vol.set_ylabel(f"Volume ({unit})")

    fig.suptitle(f"{ticker} Close & Volume")
    fig.tight_layout()

    out_path = os.path.join(ticker_dir, "price_volume.png")
    plt.savefig(out_path, dpi=200)
    plt.close()


def process_one_ticker(ticker: str, run_dir: str, period: str, interval: str) -> dict:
    # 銘柄フォルダ（output/report_xxx/7203.T/）
    ticker_dir = os.path.join(run_dir, ticker)
    ensure_dir(ticker_dir)

    df = fetch_price_history(ticker, period=period, interval=interval)

    # 生データ保存
    df.to_csv(os.path.join(ticker_dir, "price_history.csv"), index=False)

    export_summary_csv(df, ticker_dir, ticker)
    export_price_png(df, ticker_dir, ticker)
    export_price_volume_png(df, ticker_dir, ticker, interval=interval)

    return {
        "ticker": ticker,
        "status": "ok",
        "ticker_dir": ticker_dir,
    }   

def main():
    args = parse_args()

    tickers = parse_tickers(args.tickers)
    if not tickers:
        raise ValueError("ティッカーが空です。例: --tickers 7203.T,6758.T")

    ensure_dir(args.output_dir)
    run_dir = make_run_dir(args.output_dir, args.run_name)

    results = []
    for t in tickers:
        try:
            results.append(process_one_ticker(t, run_dir, args.period, args.interval))
            print(f"✅ {t}: OK")
        except Exception as e:
            results.append({"ticker": t, "status": "ng", "error": str(e)})
            print(f"❌ {t}: {e}")

    # 実行結果一覧（成功/失敗）
    result_df = pd.DataFrame(results)
    result_df.to_csv(os.path.join(run_dir, "run_result.csv"), index=False)

    # ✅ index.csv（成功した銘柄の summary.csv を集約）
    index_rows = []
    for r in results:
        if r.get("status") != "ok":
            continue
        ticker = r["ticker"]
        summary_path = os.path.join(run_dir, ticker, "summary.csv")
        if os.path.exists(summary_path):
            s = pd.read_csv(summary_path).iloc[0].to_dict()
            index_rows.append(s)

    if index_rows:
        pd.DataFrame(index_rows).to_csv(os.path.join(run_dir, "index.csv"), index=False)

    # latest 更新
    if args.latest:
        update_latest(run_dir, args.output_dir)
        print("latest を更新しました:", os.path.join(args.output_dir, "latest"))

    print("✅ 完了")
    print("出力先:", run_dir)


if __name__ == "__main__":
    main()