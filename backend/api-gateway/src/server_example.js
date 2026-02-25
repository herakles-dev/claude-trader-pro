/**
 * Example Express.js server with Prometheus metrics integration
 * This shows how to integrate metrics middleware into your server.js
 */

const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const socketIo = require('socket.io');
const http = require('http');
const axios = require('axios');

// Import metrics
const {
  metricsMiddleware,
  metricsEndpoint,
  trackWebSocketConnection,
  trackWebSocketMessage,
  trackBackendCall,
  trackDatabaseQuery,
  recordRateLimitHit,
  recordCacheAccess,
  updateDbConnections
} = require('./middleware/metrics');

const app = express();
const server = http.createServer(app);
const io = socketIo(server);

// Middleware
app.use(helmet());
app.use(cors());
app.use(express.json());

// Add metrics middleware (should be early in the stack)
app.use(metricsMiddleware);

// Metrics endpoint
app.get('/metrics', metricsEndpoint);

// Health check
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    service: 'claude-trader-api-gateway',
    version: '1.0.0'
  });
});

// Example: API endpoint with backend call tracking
app.get('/api/predictions/:asset', async (req, res) => {
  try {
    const { asset } = req.params;
    
    // Track call to claude-engine backend
    const predictions = await trackBackendCall(
      'claude-engine',
      '/predictions',
      async () => {
        const response = await axios.get(
          `${process.env.CLAUDE_ENGINE_URL}/predictions/${asset}`
        );
        return response.data;
      }
    );
    
    res.json(predictions);
  } catch (error) {
    console.error('Error fetching predictions:', error);
    res.status(500).json({ error: 'Failed to fetch predictions' });
  }
});

// Example: Database query tracking
app.get('/api/history/:asset', async (req, res) => {
  try {
    const { asset } = req.params;
    
    // Track database query
    const history = await trackDatabaseQuery(
      'select',
      'prediction_history',
      async () => {
        // Your database query here
        // const result = await db.query('SELECT * FROM prediction_history WHERE asset = $1', [asset]);
        // return result.rows;
        return []; // Placeholder
      }
    );
    
    res.json(history);
  } catch (error) {
    console.error('Error fetching history:', error);
    res.status(500).json({ error: 'Failed to fetch history' });
  }
});

// Example: Rate limiting with metrics
const rateLimit = require('express-rate-limit');

const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100,
  handler: (req, res) => {
    recordRateLimitHit(req.path);
    res.status(429).json({
      error: 'Too many requests, please try again later.'
    });
  }
});

app.use('/api/', limiter);

// WebSocket handling with metrics
io.on('connection', (socket) => {
  console.log('Client connected');
  trackWebSocketConnection(true);
  
  socket.on('subscribe', (data) => {
    trackWebSocketMessage('inbound', 'subscribe');
    console.log('Client subscribed:', data);
    
    // Handle subscription
    socket.join(data.channel);
  });
  
  socket.on('disconnect', () => {
    console.log('Client disconnected');
    trackWebSocketConnection(false);
  });
});

// Example: Broadcast with metrics
function broadcastPrediction(prediction) {
  trackWebSocketMessage('outbound', 'prediction');
  io.emit('prediction', prediction);
}

// Example: Cache usage tracking
const NodeCache = require('node-cache');
const cache = new NodeCache({ stdTTL: 600 });

async function getCachedData(key, fetchFunction) {
  const cached = cache.get(key);
  
  if (cached) {
    recordCacheAccess('memory', true);
    return cached;
  }
  
  recordCacheAccess('memory', false);
  const data = await fetchFunction();
  cache.set(key, data);
  return data;
}

// Example: Database connection monitoring
let dbPool;
if (dbPool) {
  setInterval(() => {
    updateDbConnections(dbPool.totalCount);
  }, 10000); // Update every 10 seconds
}

// Start server
const PORT = process.env.PORT || 8100;
server.listen(PORT, () => {
  console.log(`API Gateway running on port ${PORT}`);
  console.log(`Metrics available at http://localhost:${PORT}/metrics`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('SIGTERM received, shutting down gracefully');
  server.close(() => {
    console.log('Server closed');
    process.exit(0);
  });
});

module.exports = { app, server };
