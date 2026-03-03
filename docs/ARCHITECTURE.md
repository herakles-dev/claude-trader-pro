# ClaudeTrader Pro - Complete System Architecture

**Version:** 1.1.0
**Last Updated:** January 18, 2026
**Status:** ✅ Fully Operational

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Service Components](#service-components)
4. [Data Flow](#data-flow)
5. [API Endpoints](#api-endpoints)
6. [Database Schema](#database-schema)
7. [Frontend Architecture](#frontend-architecture)
8. [Deployment](#deployment)
9. [Monitoring & Observability](#monitoring--observability)
10. [Troubleshooting](#troubleshooting)

---

## 🎯 System Overview

**ClaudeTrader Pro** is an AI-powered cryptocurrency trading intelligence platform that provides real-time market predictions using Claude 3.5 Haiku AI model combined with comprehensive market data analysis.

### Key Features
- **AI-Powered Predictions**: Claude 3.5 Haiku generates trading signals based on multi-source data
- **Real-time Updates**: WebSocket connections for live market data and prediction updates
- **Cost Tracking**: Monitors Claude API usage and costs ($0.0001 per prediction)
- **Multi-Source Data**: Aggregates market data, sentiment, technical indicators, and derivatives
- **Production Ready**: Health checks, metrics, logging, and error handling

### Technology Stack

**Backend:**
- Node.js 18+ (API Gateway)
- Python 3.11 (Claude Engine)
- FastAPI (Claude Engine framework)
- Express.js (API Gateway framework)
- Socket.IO (Real-time WebSocket)

**Database:**
- PostgreSQL 14+ (primary data store)
- Connection pooling with pg driver

**AI/ML:**
- Google Gemini 2.0 Flash (default) OR Anthropic Claude 3.5 Haiku (configurable via AI_PROVIDER env)
- Unified Crypto Data API (market data aggregation)
- FRED macro economic indicators integration
- Multi-timeframe technical analysis via TAAPI Pro

**Trading:**
- OctoBot paper trading engine (port 8109)
- Auto-execution when prediction confidence >= 50%
- PostgreSQL trade sync and tracking

**Frontend:**
- React 18 with Vite
- TanStack Query (React Query) for data fetching
- Tailwind CSS for styling
- Recharts for data visualization

**Infrastructure:**
- Docker & Docker Compose
- Nginx reverse proxy
- Cloudflare Tunnel (cloudflared)
- Loki logging (structured logs)
- Prometheus metrics

---

## 🏗️ Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Internet / Users                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                  ┌──────────▼────────────┐
                  │  Cloudflare Tunnel    │
                  │  (cloudflared)        │
                  └──────────┬────────────┘
                             │
                  ┌──────────▼────────────┐
                  │   Nginx Reverse Proxy │
                  │   api.your-domain.example.com  │
                  └──────────┬────────────┘
                             │
                  ┌──────────▼────────────┐
                  │   Frontend (React)    │
                  │   Static Files        │
                  │   /var/www/...        │
                  └──────────┬────────────┘
                             │
                             │ API Requests
                             │
        ┌────────────────────▼─────────────────────┐
        │     API Gateway (Node.js/Express)       │
        │     Port: 3001                            │
        │                                           │
        │  • Health checks                          │
        │  • Request routing                        │
        │  • Rate limiting                          │
        │  • WebSocket server (Socket.IO)           │
        │  • Database connection (PostgreSQL)       │
        │  • Metrics & logging                      │
        └────────┬──────────────────┬───────────────┘
                 │                  │
                 │                  │ WebSocket
                 │                  │ (real-time)
                 │                  │
    ┌────────────▼────────────┐    │
    │  Claude Engine (Python)  │    │
    │  Port: 8000              │    │
    │                          │    │
    │  • FastAPI framework     │    │
    │  • Claude API client     │    │
    │  • Unified Data API      │    │
    │  • Prediction logic      │    │
    │  • Cost tracking         │    │
    │  • Database ORM          │    │
    └────────┬─────────────────┘    │
             │                       │
             │                       │
    ┌────────▼───────────────────────▼──────┐
    │        PostgreSQL Database            │
    │        Port: 5432                     │
    │                                       │
    │  Schema: public                      │
    │  Table: trading_predictions          │
    │  • Prediction storage                │
    │  • Cost tracking                     │
    │  • Historical data                   │
    └───────────────────────────────────────┘

External Services:
┌─────────────────────────────────────────────┐
│  • Anthropic Claude / Google Gemini (AI)    │
│  • Binance/Bybit (market data)              │
│  • Reddit API (sentiment)                   │
│  • Fear & Greed Index                       │
│  • FRED API (macro economic indicators)     │
│  • DeFiLlama (TVL data)                     │
│  • TAAPI Pro (technical indicators)         │
└─────────────────────────────────────────────┘
```

---

## 🔧 Service Components

### 1. API Gateway (`claude-trader-gateway`)

**Location:** `backend/api-gateway/`
**Port:** 3001
**Technology:** Node.js 18 + Express.js
**Container:** `claude-trader-gateway`

#### Responsibilities
- Routes all frontend API requests
- Proxies prediction requests to Claude Engine
- Manages WebSocket connections for real-time updates
- Database connection for predictions retrieval
- Health checks and system status aggregation
- Rate limiting and security middleware
- Prometheus metrics exposure

#### Key Endpoints
```javascript
GET  /api/health                    // System health check
GET  /api/predictions               // List predictions
GET  /api/predictions/:id           // Get specific prediction
POST /api/predictions/generate      // Trigger new prediction
GET  /api/websocket/stats           // WebSocket statistics
GET  /api/metrics                   // Prometheus metrics
```

#### Configuration
```javascript
// .env
NODE_ENV=production
PORT=3001
CLAUDE_ENGINE_URL=http://claude-trader-engine:8000
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=trader_db
POSTGRES_USER=trader
POSTGRES_PASSWORD=your-password-here
```

#### Health Check Logic
```javascript
// GET /api/health response
{
  "success": true,
  "data": {
    "status": "healthy",
    "service": "claude-trader-api-gateway",
    "version": "1.0.0",
    "uptime": 3600.5,
    "timestamp": "2025-11-11T15:00:00.000Z",
    "database": "connected",          // PostgreSQL status
    "claudeEngine": "available",       // Claude Engine status
    "websocket": {
      "connectedClients": 0,
      "subscriptions": [],
      "totalSubscriptions": 0
    }
  }
}
```

---

### 2. Claude Engine (`claude-trader-engine`)

**Location:** `backend/claude-engine/`
**Port:** 8000
**Technology:** Python 3.11 + FastAPI
**Container:** `claude-trader-engine`

#### Responsibilities
- Generates AI-powered trading predictions using Claude 3.5 Haiku
- Fetches and aggregates market data from multiple sources
- Calculates technical indicators and sentiment scores
- Stores predictions in PostgreSQL with full metadata
- Tracks API costs and token usage
- Exposes health checks and metrics

#### Architecture
```
claude-engine/
├── app/
│   ├── main.py                     // FastAPI application entry
│   ├── models/
│   │   └── prediction.py           // SQLAlchemy ORM models
│   ├── schemas/
│   │   └── prediction.py           // Pydantic request/response schemas
│   ├── repositories/
│   │   └── prediction_repo.py      // Database access layer
│   ├── services/
│   │   ├── claude_client.py        // Anthropic API client
│   │   ├── unified_data_client.py  // Market data aggregation
│   │   └── prompt_templates.py     // Claude prompt engineering
│   └── routers/
│       └── predictions.py          // API endpoints
└── requirements.txt                // Python dependencies
```

#### Key Endpoints
```python
POST   /api/v1/predict              // Generate new prediction
GET    /api/v1/predictions          // List predictions
GET    /api/v1/predictions/{id}     // Get specific prediction
GET    /api/v1/health               // Service health check
GET    /api/v1/costs                // Cost tracking summary
GET    /api/v1/accuracy             // Prediction accuracy metrics
GET    /metrics                     // Prometheus metrics
```

#### Prediction Flow
1. **Receive Request**: `POST /api/v1/predict` with `{symbol, strategy}`
2. **Fetch Market Data**: Call Unified Data API for multi-source data
   - Market prices (Binance, CoinGecko)
   - Sentiment scores (Reddit, Fear & Greed)
   - Technical indicators (RSI, MACD, EMA via TAAPI Pro)
   - Derivatives data (funding rates, open interest)
   - Macro economic data (DXY, S&P 500, VIX, Treasury yields via FRED)
   - TVL data (DeFiLlama)
3. **Format Context**: Build rich prompt with market snapshot
4. **Call Claude API**: Generate prediction with Claude 3.5 Haiku
5. **Parse Response**: Extract prediction, confidence, reasoning
6. **Calculate Cost**: Track token usage and API cost
7. **Store in Database**: Save prediction with full metadata
8. **Return Response**: Send prediction back to client

#### Claude API Integration
```python
# Model Configuration
MODEL = "claude-3-5-haiku-20241022"
MAX_TOKENS = 500
PRICE_INPUT = $0.25 per 1M tokens
PRICE_OUTPUT = $1.25 per 1M tokens
AVERAGE_COST = ~$0.0001 per prediction
```

#### Database Schema
```sql
CREATE TABLE trading_predictions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    prediction_type VARCHAR(10) NOT NULL,  -- 'up' or 'down'
    confidence FLOAT NOT NULL,              -- 0.0 to 1.0
    reasoning TEXT NOT NULL,
    market_context JSONB NOT NULL,
    claude_model VARCHAR(50) NOT NULL,
    prompt_version VARCHAR(10) NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cached_tokens INTEGER DEFAULT 0,
    total_cost_usd NUMERIC(12, 8) NOT NULL,
    api_latency_ms INTEGER NOT NULL,
    strategy VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_predictions_symbol ON trading_predictions(symbol);
CREATE INDEX idx_predictions_created ON trading_predictions(created_at DESC);
CREATE INDEX idx_predictions_type ON trading_predictions(prediction_type);
```

#### Health Check Response
```json
{
  "status": "degraded",
  "timestamp": "2025-11-11T15:00:00.000Z",
  "database": "healthy",
  "unified_api": "unhealthy",       // External API status
  "claude_api": "healthy"           // Anthropic API status
}
```

**Note:** Claude Engine returns status 503 when degraded, but API Gateway considers status 200 as "available".

---

### 3. Frontend (React SPA)

**Location:** `frontend/`
**Deployed:** `/var/www/your-domain/`
**Technology:** React 18 + Vite + TailwindCSS
**Public URL:** `https://your-domain.example.com`

#### Architecture
```
frontend/
├── src/
│   ├── components/
│   │   ├── SystemHealth.jsx        // Service status display
│   │   ├── PredictionList.jsx      // Prediction history
│   │   ├── PredictionCard.jsx      // Individual prediction
│   │   └── Dashboard.jsx           // Main dashboard
│   ├── services/
│   │   └── api.js                  // Axios API client
│   ├── hooks/
│   │   └── useWebSocket.js         // WebSocket hook
│   └── main.jsx                    // React entry point
└── vite.config.js                  // Build configuration
```

#### Key Components

**SystemHealth Component**
- Displays real-time service status
- Polls `/api/health` every 30 seconds
- Shows 4 services: API Gateway, WebSocket, Market Data, AI Engine
- Color-coded status indicators (green/yellow/red)

**Data Fetching Strategy**
```javascript
// React Query for API calls
const { data, isLoading } = useQuery(
  'system-health',
  () => systemAPI.getHealth(),
  {
    refetchInterval: 30000,  // 30 seconds
    select: (response) => response.data.data  // Unwrap envelope
  }
);
```

**API Client Configuration**
```javascript
// /src/services/api.js
const API_BASE_URL = '/api';  // Relative to same domain

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' }
});
```

#### Status Display Logic
```javascript
const services = [
  {
    name: 'API Gateway',
    status: health?.status === 'healthy' || health?.status === 'degraded' 
      ? 'online' : 'offline',
    icon: '🌐'
  },
  {
    name: 'WebSocket',
    status: wsConnected ? 'online' : 'offline',
    icon: '⚡'
  },
  {
    name: 'Market Data',
    status: health?.claudeEngine === 'available' ? 'online' : 'offline',
    icon: '📊'
  },
  {
    name: 'AI Engine',
    status: health?.claudeEngine === 'available' ? 'online' : 'offline',
    icon: '🤖'
  }
];
```

---

## 📊 Data Flow

### 1. Health Check Flow
```
Frontend (SystemHealth.jsx)
  │
  ├─> API Request: GET /api/health
  │
  ▼
API Gateway (api.js)
  │
  ├─> Check PostgreSQL: SELECT 1
  ├─> Call Claude Engine: GET /api/v1/health
  │
  ▼
Claude Engine (predictions.py)
  │
  ├─> Check Database
  ├─> Check Unified API
  ├─> Check Claude API (test request)
  │
  ▼
Response Envelope:
{
  success: true,
  data: {
    status: "healthy",
    database: "connected",
    claudeEngine: "available",
    websocket: { connectedClients: 0 }
  }
}
  │
  ▼
Frontend Updates UI:
✅ API Gateway: online
✅ WebSocket: online
✅ Market Data: online
✅ AI Engine: online
```

### 2. Prediction Generation Flow
```
User clicks "Generate Prediction"
  │
  ▼
Frontend: POST /api/predictions/generate
  │
  ▼
API Gateway (api.js)
  │
  ├─> Proxy to Claude Engine: POST /api/v1/predict
  │
  ▼
Claude Engine (predictions.py)
  │
  ├─> Unified Data Client
  │   ├─> Fetch Binance market data
  │   ├─> Fetch Reddit sentiment
  │   ├─> Calculate technical indicators
  │   └─> Aggregate funding rates
  │
  ├─> Format market context (prompt engineering)
  │
  ├─> Claude API Client
  │   └─> anthropic.messages.create()
  │        Model: claude-3-5-haiku-20241022
  │        Max Tokens: 500
  │
  ├─> Parse JSON response
  │   {
  │     "prediction": "up",
  │     "confidence": 75,
  │     "reasoning": "..."
  │   }
  │
  ├─> Calculate cost ($0.0001)
  │
  ├─> Store in PostgreSQL
  │
  ▼
Response to Frontend:
{
  id: 123,
  symbol: "BTC/USDT",
  prediction_type: "up",
  confidence: 0.75,
  reasoning: "...",
  total_cost_usd: 0.0001,
  api_latency_ms: 850
}
  │
  ▼
Frontend displays prediction
WebSocket broadcasts to all connected clients
```

---

## 🔌 API Endpoints

### API Gateway Endpoints

#### `GET /api/health`
**Description:** System health check  
**Response:**
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "service": "claude-trader-api-gateway",
    "version": "1.0.0",
    "uptime": 3600.5,
    "timestamp": "2025-11-11T15:00:00.000Z",
    "database": "connected",
    "claudeEngine": "available",
    "websocket": {
      "connectedClients": 0,
      "subscriptions": [],
      "totalSubscriptions": 0
    }
  }
}
```

#### `GET /api/predictions`
**Description:** List recent predictions  
**Query Parameters:**
- `limit` (optional): Max results (default: 50)
- `offset` (optional): Pagination offset (default: 0)
- `symbol` (optional): Filter by symbol (e.g., "BTC/USDT")

**Response:**
```json
{
  "success": true,
  "data": {
    "predictions": [
      {
        "id": 1,
        "symbol": "BTC/USDT",
        "prediction_type": "up",
        "confidence": 0.75,
        "reasoning": "Strong bullish momentum...",
        "total_cost_usd": 0.0001,
        "created_at": "2025-11-11T15:00:00.000Z"
      }
    ],
    "total": 1,
    "limit": 50,
    "offset": 0
  }
}
```

#### `POST /api/predictions/generate`
**Description:** Generate new prediction  
**Request Body:**
```json
{
  "symbol": "BTC/USDT",
  "strategy": "conservative"  // or "aggressive"
}
```

**Response:** See prediction object above

### Claude Engine Endpoints

#### `GET /api/v1/health`
**Description:** Claude Engine health check  
**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-11T15:00:00.000Z",
  "database": "healthy",
  "unified_api": "healthy",
  "claude_api": "healthy"
}
```

#### `POST /api/v1/predict`
**Description:** Generate AI prediction  
**Request Body:**
```json
{
  "symbol": "BTC/USDT",
  "strategy": "conservative"
}
```

#### `GET /api/v1/costs`
**Description:** Cost tracking summary  
**Query Parameters:**
- `days` (optional): Number of days to summarize (default: 7)

**Response:**
```json
{
  "period_days": 7,
  "total_predictions": 123,
  "total_cost_usd": 0.0123,
  "avg_cost_per_prediction": 0.0001,
  "total_input_tokens": 123456,
  "total_output_tokens": 45678
}
```

---

## 🚀 Deployment

### Production Deployment

**Infrastructure:**
- Docker containers managed by Docker Compose
- Nginx reverse proxy (port 443 → 3001)
- Cloudflare Tunnel for external access
- PostgreSQL database (existing Hercules platform instance)

**Container Details:**
```bash
# API Gateway
Container: claude-trader-gateway
Image: Built from /backend/api-gateway/Dockerfile
Port: 0.0.0.0:3001->3001/tcp
Network: claude-trader_default
Status: Up, Healthy

# Claude Engine
Container: claude-trader-engine
Image: Built from /backend/claude-engine/Dockerfile
Port: 0.0.0.0:8000->8000/tcp
Network: claude-trader_default
Status: Up, Healthy
```

**Deployment Commands:**
```bash
# Start services
docker-compose -f docker/docker-compose.prod.yml up -d

# Check status
docker ps --filter "name=claude-trader"

# View logs
docker logs claude-trader-gateway --tail 100
docker logs claude-trader-engine --tail 100

# Restart services
docker restart claude-trader-gateway
docker restart claude-trader-engine

# Deploy frontend
cd frontend
npm run build
sudo rm -rf /var/www/your-domain/*
sudo cp -r dist/* /var/www/your-domain/
```

**Environment Variables:**
```bash
# .env (production)
NODE_ENV=production
ANTHROPIC_API_KEY=your-anthropic-api-key-here
DATABASE_URL=postgresql://trader:your-password-here@postgres:5432/trader_db
CLAUDE_ENGINE_URL=http://claude-trader-engine:8000
```

### Hot Reload Development

**For development with hot reload:**
```bash
# Use dev compose file with volume mounts
docker-compose -f docker-compose.simple-dev.yml up -d

# Changes to /backend/claude-engine/app/* auto-reload
# Changes to /backend/api-gateway/src/* require restart
```

---

## 📈 Monitoring & Observability

### Health Checks
- **API Gateway:** `curl http://localhost:3001/api/health`
- **Claude Engine:** `curl http://localhost:8000/api/v1/health`
- **Frontend:** `curl https://your-domain.example.com/`

### Metrics
- **Prometheus endpoints:**
  - API Gateway: `http://localhost:3001/api/metrics`
  - Claude Engine: `http://localhost:8000/metrics`

### Logging
- **Structured JSON logs** sent to Loki
- **Log levels:** DEBUG, INFO, WARN, ERROR
- **Access via:** `docker logs <container>`

### Key Metrics Tracked
- Request counts and latency
- Prediction generation count
- Claude API costs (cumulative)
- Database query performance
- WebSocket connection count
- Circuit breaker state
- Error rates by endpoint

---

## 🛠️ Troubleshooting

### Common Issues

#### 1. All Services Show "Offline" in Frontend
**Symptom:** Frontend System Status shows all red  
**Cause:** Frontend React Query `select` function not unwrapping API response envelope correctly  
**Fix:** Update `SystemHealth.jsx`:
```javascript
select: (response) => response.data.data  // Unwrap double .data
```

#### 2. Claude Engine Shows "Unavailable"
**Symptoms:**
- API Gateway health shows `claudeEngine: "unavailable"`
- Claude Engine logs: `'Anthropic' object has no attribute 'messages'`

**Cause:** Old Anthropic SDK version (0.8.1) vs new API code  
**Fix:**
```bash
# Update requirements.txt
anthropic>=0.40.0

# Upgrade in container
docker exec claude-trader-engine pip install --upgrade 'anthropic>=0.40.0'
docker restart claude-trader-engine
```

#### 3. Health Check Returns: "object SystemHealth can't be used in 'await' expression"
**Cause:** Trying to `await` synchronous `get_system_health()` method  
**Fix:** Remove `await` in `unified_data_client.py`:
```python
# Wrong
health = await self.api.get_system_health()

# Correct
health = self.api.get_system_health()
```

#### 4. Unified API Shows "Unhealthy"
**Expected Behavior:** Shows unhealthy until first prediction request  
**Reason:** Health stats are populated after external API calls  
**Not a Bug:** This is normal - will become healthy after generating predictions

#### 5. Prediction Request Times Out
**Cause:** External API calls (Binance, Reddit) taking too long  
**Troubleshooting:**
```bash
# Check Claude Engine logs
docker logs claude-trader-engine --tail 50

# Test external API directly
docker exec claude-trader-engine python -c "
from app.services.unified_data_client import UnifiedDataClient
import asyncio
client = UnifiedDataClient()
result = asyncio.run(client.get_market_snapshot('BTC/USDT'))
print(result)
"
```

### Debug Commands

```bash
# Check container health
docker ps --filter "name=claude-trader"

# Check API Gateway health
curl -s http://localhost:3001/api/health | jq '.'

# Check Claude Engine health
curl -s http://localhost:8000/api/v1/health | jq '.'

# Check database connection
docker exec claude-trader-engine python -c "
from app.models.prediction import DatabaseConfig
from sqlalchemy import create_engine, text
engine = create_engine(DatabaseConfig.get_connection_string())
with engine.connect() as conn:
    result = conn.execute(text('SELECT COUNT(*) FROM trading_predictions'))
    print(f'Predictions in database: {result.scalar()}')
"

# Check Anthropic SDK version
docker exec claude-trader-engine pip show anthropic

# Test Claude API directly
docker exec claude-trader-engine python -c "
from anthropic import Anthropic
import os
client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
response = client.messages.create(
    model='claude-3-5-haiku-20241022',
    max_tokens=10,
    messages=[{'role': 'user', 'content': 'Test'}]
)
print('Claude API: OK')
"
```

---

## ✅ System Status

**Current State:** ✅ Fully Operational

| Service | Status | Port | Health Endpoint |
|---------|--------|------|-----------------|
| Frontend | ✅ Online | 443 (HTTPS) | `https://your-domain.example.com/` |
| API Gateway | ✅ Online | 3001 | `/api/health` |
| Claude Engine | ✅ Online | 8000 | `/api/v1/health` |
| PostgreSQL | ✅ Connected | 5432 | N/A |
| WebSocket | ✅ Active | 3001 | `/api/websocket/stats` |

**Fixed Issues:**
1. ✅ Frontend React Query data envelope unwrapping
2. ✅ Anthropic SDK version compatibility (upgraded 0.8.1 → 0.72.0)
3. ✅ Async/await bug in unified_data_client health check
4. ✅ Health check response structure mismatch (`.sources` → `.api_health`)

**Known Limitations:**
- Unified API shows "unhealthy" until first prediction request (expected behavior)
- Prediction requests may timeout if external APIs are slow (network-dependent)
- Claude Engine returns 503 when degraded, but Gateway considers it "available" (by design)

---

**Document Created:** November 11, 2025
**Author:** Claude Code AI Assistant
**Last Verified:** January 18, 2026

For updates or issues, refer to project README and GitHub issues.
