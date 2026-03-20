# ⬡ COMMODEX

**COMMODEX** is an AI-assisted MCX Commodity Signal Platform. Built on Python and Streamlit, it orchestrates a three-agent LLM pipeline to analyze market data, generate trading signals, and enforce strict automated risk management through a pre-defined guardrail system.

The platform relies on live data fetched from the Groww API and relevant news from the Tavily API, currently fine-tuned for the **Gold Mini (GOLDM)** and **Crude Oil Mini (CRUDEOILM)** contracts.

## ✨ Features

- **3-Agent AI Pipeline**: 
  - **Agent 1 (Market Analyst)**: Determines the market regime, sentiment, and key support/resistance levels.
  - **Agent 2 (Signal Generator)**: Generates actionable trading signals (BUY/SELL/HOLD) based on market analysis.
  - **Agent 3 (Risk Assessor)**: Computes precise risk parameters including Entry, targets, and exit conditions.
- **Robust Risk Engine (Guardrails)**: Implements 10 immutable rules to block unviable trades (e.g., minimum confidence, daily loss limits, post-cutoff intraday restrictions, R:R limits, and expiry blackout weeks).
- **Technical Engine Integration**: Dynamically calculates MACD, Bollinger Bands, RSI, ATR, Pivots and EMA from live chart data.
- **Provider Agnostic LLM Client**: Native support for **OpenAI** (demo mode) and **Anthropic Claude** (paper/production mode) models.
- **Local Persistence**: Tracks all your history securely in a local SQLite database (`commodex.db`).

## 🚀 Getting Started

### Prerequisites

- **Python 3.12+**
- Groww Account (for API connection)
- LLM API Keys (OpenAI / Anthropic)
- Tavily API Key (for news context)

### 1. Installation

Clone the repository and install the dependencies:
```bash
git clone https://github.com/chaudharyviv/commodex.git
cd commodex
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configuration (`.env`)

Create a `.env` file in the root directory by renaming or copying an example `.env.example` if it exists. Provide your API keys and configuration parameters:

```ini
# Groww API
GROWW_API_KEY=your_groww_api_key_here
GROWW_TOTP_SECRET=your_groww_totp_secret_here

# LLM Providers
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# News Provider
TAVILY_API_KEY=your_tavily_api_key_here

# Trading and Risk Parameters
TRADING_MODE=demo
CAPITAL_INR=100000
RISK_PCT_PER_TRADE=2.5
MAX_OPEN_POSITIONS=2
DAILY_LOSS_LIMIT_PCT=5.0
```

### 3. Run the App

Start the Streamlit application:
```bash
streamlit run app.py
```

Open `http://localhost:8501` to view your dashboard.

## 🛡️ Guardrails / Risk Engine

COMMODEX employs an independent internal Risk Engine that ensures the LLMs do not propose unsafe trades. The 10 rules it observes are:

1. Daily Loss Limit
2. Max Open Positions
3. Minimum Confidence Threshold 
4. Valid Market Hours (IST)
5. Impactful Event Restraints 
6. Minimum Risk-Reward Ratio
7. Production Safety Validation check
8. End of Contract Expiry Blackout
9. INR/USD Volatility Gates
10. Intraday Session Hour Cutoffs

## 📖 Disclaimer

**DISCLAIMER**: This application is built for personal, educational, and testing purposes only. COMMODEX does **not** provide qualified financial advice. Trading commodities on margin involves substantial risk and is not suitable for all investors. Never trade with money you cannot afford to lose. Always thoroughly backtest systems and rely on paper trading prior to considering real deployment. 

The developer of COMMODEX assumes no responsibility for any financial losses or damages incurred.

## 📄 License

This project is licensed under the MIT License.
