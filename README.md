# Claude Trader Pro

AI-powered cryptocurrency trading platform with real-time market analysis, confidence-calibrated predictions, and automated trade execution.

## Architecture

- **Claude Engine** (Python/FastAPI) — AI prediction service with multi-provider support (Claude, Gemini), confidence calibration, backtesting, and risk management
- **API Gateway** (Node.js/Express) — WebSocket streaming, REST API routing, authentication middleware, rate limiting
- **Frontend** (React) — Real-time analytics dashboard with interactive charts, trade history, and performance metrics
- **Monitoring** (Grafana/Prometheus) — Custom dashboards for prediction accuracy, P&L tracking, and system health

## Key Features

- Multi-model AI predictions with historical confidence tracking
- Real-time WebSocket market data streaming
- Automated trade execution with configurable risk limits
- Backtesting engine for strategy validation
- Pattern analysis across multiple timeframes

## Tech Stack

Python, FastAPI, SQLAlchemy, PostgreSQL, Node.js, Express, WebSocket, React, Docker, Grafana, Prometheus

## Running Locally

```bash
cp .env.example .env
# Fill in API keys and database credentials
docker-compose up -d
```

## Project Structure

```
backend/
  claude-engine/     # Python AI prediction service
    app/
      services/      # Core business logic
      models/        # SQLAlchemy models
  api-gateway/       # Node.js API + WebSocket server
    src/
      routes/        # REST endpoints
      middleware/     # Auth, rate limiting
      services/      # Business logic
frontend/
  src/
    components/      # React components
    hooks/           # Custom hooks
    context/         # State management
    pages/           # Route pages
docs/                # Architecture docs
docker/              # Docker configs
tests/               # Test suites
```
