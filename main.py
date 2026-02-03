from __future__ import annotations

import os
from datetime import datetime

import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt

OUTPUT_DIR = "output"


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def make_run_dir(base_dir: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(base_dir, f"report_{ts}")
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def _normalize_yfinance_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    yfinance の download は環境/バージョンによって列が MultiIndex になることがある。
    その場合でも Open/High/Low/Close/Volume を 1段に揃える。
    """
    if isinstance(df.columns, pd.MultiIndex):
        # どっちの階層に "Close" があるかで判定
        level0 = df.columns.get_level_values(0)
        level1 = df.columns.get_level_values(1)

        if "Close" in set(level0):
            df.columns = level0
        elif "Close" in set(level1):
            df.columns = level1
        else:
            # 最後の保険：文字列化して平坦化
            df.columns = ["_".join(map(str, c)).strip() for c in df.columns.to_list()]

    return df


def fetch_price_history(ticker: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
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

    # index（日付）を列にする
    df = df.reset_index()

    # 必要列だけに絞る
    cols = [c for c in ["Date", "Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    df = df[cols].copy()

    return df


def export_summary_csv(df: pd.DataFrame, run_dir: str, ticker: str):
    # 最終行（Series）
    latest = df.iloc[-1]

    # latest["Close"] が Series になってしまう環境の保険
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

    summary_path = os.path.join(run_dir, "summary.csv")
    summary.to_csv(summary_path, index=False)


def export_price_png(df: pd.DataFrame, run_dir: str, ticker: str):
    if "Date" not in df.columns or "Close" not in df.columns:
        raise ValueError("Date / Close 列がありません。取得データの形式を確認してください。")

    plt.figure(figsize=(10, 5))
    plt.plot(df["Date"], df["Close"])
    plt.title(f"{ticker} Close Price")
    plt.xlabel("Date")
    plt.ylabel("Close")
    plt.tight_layout()

    out_path = os.path.join(run_dir, "price.png")
    plt.savefig(out_path, dpi=200)
    plt.close()


def main():
    # まずは固定で最小（日本株ティッカー）
    ticker = "7203.T"
    period = "6mo"
    interval = "1d"

    ensure_output_dir()
    run_dir = make_run_dir(OUTPUT_DIR)

    df = fetch_price_history(ticker, period=period, interval=interval)

    # 生データ
    df.to_csv(os.path.join(run_dir, "price_history.csv"), index=False)

    export_summary_csv(df, run_dir, ticker)
    export_price_png(df, run_dir, ticker)

    print("✅ 完了")
    print("出力先:", run_dir)


if __name__ == "__main__":
    main()