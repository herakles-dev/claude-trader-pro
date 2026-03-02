# Claude Trader Pro

AI-powered cryptocurrency trading platform with real-time market analysis, confidence-calibrated predictions, and automated trade execution.

## Architecture

```
                    React Dashboard
                    (real-time charts, trade history)
                          |
                     WebSocket + REST
                          |
                    API Gateway (Node.js/Express)
                    auth, rate limiting, routing
                          |
              +-----------+-----------+
              |                       |
      Claude Engine            PostgreSQL
      (Python/FastAPI)         (predictions, trades,
      AI predictions,          confidence history)
      risk management,
      backtesting
              |
      +-------+-------+
      |               |
  Claude API     Gemini API
  (predictions)  (predictions)
```

## Key Features

- **Multi-model AI predictions** — Claude Sonnet 4 and Gemini 2.0 Flash providers with automatic confidence calibration against historical accuracy
- **Real-time WebSocket streaming** — Live market data, prediction updates, and trade notifications pushed to the dashboard
- **Risk management engine** — Configurable daily loss limits, max drawdown, position sizing, volatility-adjusted exposure, cooldown periods
- **Backtesting** — Run prediction strategies against historical data with configurable parameters
- **Pattern analysis** — Multi-timeframe technical analysis via TAAPI Pro integration
- **OctoBot integration** — Automated trade execution through OctoBot with paper trading support

## Tech Stack

Python, FastAPI, SQLAlchemy, PostgreSQL, Node.js, Express, WebSocket, React, Docker, Grafana, Prometheus

## Running Locally

```bash
cp .env.example .env
# Fill in API keys and database credentials
docker compose -f docker/docker-compose.dev.yml up -d
```

Requires: Docker, API keys for at least one AI provider (Claude or Gemini).

## Project Structure

```
backend/
  claude-engine/        # Python AI prediction service
    app/
      services/         # 16 service modules (AI clients, prediction worker,
                        #   risk mgmt, backtesting, confidence calibration,
                        #   pattern analysis, trade tracking, scheduler)
      models/           # SQLAlchemy models (predictions, trades, cycles)
  api-gateway/          # Node.js API + WebSocket server
    src/
      routes/           # REST endpoints (predictions, market, signals, config)
      middleware/        # Auth, rate limiting, request validation
      services/         # WebSocket broadcasting, data aggregation
frontend/
  src/
    components/         # Analytics charts, prediction cards, trade tables
    hooks/              # WebSocket connection, data fetching
    context/            # App state, WebSocket state, theme
    pages/              # Dashboard, predictions, backtesting, settings
docs/                   # ARCHITECTURE.md, API_REFERENCE.md
docker/                 # Compose files (dev, prod, simple), Grafana dashboards,
                        #   Prometheus scrape configs and alert rules
tests/                  # Python + JS test suites across all layers
```

---

Built by [D. Michael Piscitelli](https://github.com/HeraclesBass) | [herakles.dev](https://herakles.dev)
