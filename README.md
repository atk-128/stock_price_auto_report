# stock_price_auto_report

株価データを取得し、CSVとグラフを自動生成するCLIツールです。

## 使い方（CLI）

### 1) 単体銘柄を実行

```bash
python3 main.py --tickers 7203.T

python3 main.py --tickers 7203.T,6758.T,9984.T

python3 main.py \
  --tickers 7203.T,6758.T \
  --period 6mo \
  --interval 1d

  python3 main.py \
  --tickers 7203.T,6758.T \
  --run-name my_test_run

  python3 main.py \
  --tickers 7203.T,6758.T \
  --latest

  ---

## 出力フォルダ例（READMEに必須）

```md
## 出力フォルダ構成

```text
output/
├─ report_20260204_121505_my_test_run/
│  ├─ 7203.T/
│  │  ├─ price_history.csv
│  │  ├─ price.png
│  │  └─ summary.csv
│  ├─ 6758.T/
│  │  ├─ price_history.csv
│  │  ├─ price.png
│  │  └─ summary.csv
│  └─ run_result.csv
│
├─ latest/               # --latest 指定時に更新
│  ├─ 7203.T/
│  ├─ 6758.T/
│  └─ run_result.csv
│
└─ LATEST_RUN.txt