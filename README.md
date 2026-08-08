# 🥇 Gold Price Bot

An automated Telegram bot that collects daily gold prices, analyzes short-term price trends, and sends a daily report to Telegram.

The bot was developed to automate the process of monitoring gold prices from multiple sources instead of manually checking different websites every morning.

## 🚀 Key Features

- Automatically collects daily gold prices from multiple sources.
- Tracks SJC, BTMC and DOJI gold prices.
- Retrieves international gold prices (XAU/USD).
- Retrieves USD/VND exchange rates.
- Compares current prices with previous-day and 7-day prices.
- Calculates SMA3 and SMA7 to identify short-term trends.
- Estimates the difference between domestic and international gold prices after conversion to VND.
- Sends an automated daily report directly to Telegram.
- Runs automatically every morning using GitHub Actions.
- Continues running even when one data source is temporarily unavailable.

## 🛠️ Technologies

- **Python**
- **GitHub Actions**
- **Telegram Bot API**
- **JSON**
- **REST APIs / Data Sources**
- **vnstock**

## 📊 Data Sources

| Source | Data | Status |
|---|---|---|
| SJC | Domestic gold prices | Available |
| BTMC | Domestic gold prices | Available |
| DOJI | Domestic gold prices | Available |
| GoldPrice.org | International gold price (XAU/USD) | Available |
| Open ER API | USD/VND exchange rate | Available |
| PNJ | Domestic gold prices | Not implemented |

> Some data sources, particularly DOJI, rely on unofficial APIs and may become unavailable if the source changes its website or API structure.

## 📈 Trend Analysis

The bot currently performs several basic analyses based on SJC gold prices:

- Percentage change compared with the previous day.
- Percentage change compared with 7 days ago.
- **SMA3** – 3-day simple moving average.
- **SMA7** – 7-day simple moving average.
- Short-term trend classification: **Upward / Downward / Sideways**.
- Difference between domestic gold prices and international gold prices converted to VND.

These metrics are intended to provide a quick overview of recent price movements rather than predict future market movements.

## 🤖 Telegram Report

After collecting and processing the data, the bot automatically sends a daily summary to a configured Telegram chat.

The report includes:

- Current gold prices
- Daily price changes
- 7-day price changes
- Short-term trend
- Domestic vs. international price difference

## ⚙️ Automation

The bot runs automatically through **GitHub Actions**.

Default schedule:

```yaml
cron: "0 1 * * *"
