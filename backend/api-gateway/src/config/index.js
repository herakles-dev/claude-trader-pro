/**
 * Configuration Management
 * Centralized configuration with validation
 */

require('dotenv').config();

// Validate required environment variables
const requiredEnvVars = [
  'NODE_ENV',
  'PORT',
  'CLAUDE_ENGINE_URL'
];

const missingEnvVars = requiredEnvVars.filter(varName => !process.env[varName]);

if (missingEnvVars.length > 0) {
  console.error(`Missing required environment variables: ${missingEnvVars.join(', ')}`);
  process.exit(1);
}

const config = {
  // Application
  app: {
    name: 'claude-trader-api-gateway',
    version: '1.0.0',
    env: process.env.NODE_ENV || 'development',
    port: parseInt(process.env.PORT || '8100', 10)
  },

  // Backend Services
  services: {
    claudeEngine: {
      url: process.env.CLAUDE_ENGINE_URL,
      timeout: parseInt(process.env.CLAUDE_ENGINE_TIMEOUT || '120000', 10), // 2 minutes for external API calls
      retries: parseInt(process.env.CLAUDE_ENGINE_RETRIES || '3', 10)
    }
  },

  // Database
  database: {
    host: process.env.DB_HOST || 'localhost',
    port: parseInt(process.env.DB_PORT || '5432', 10),
    name: process.env.DB_NAME || 'claudetrader',
    user: process.env.DB_USER || 'postgres',
    password: process.env.DB_PASSWORD || 'postgres',
    maxConnections: parseInt(process.env.DB_MAX_CONNECTIONS || '20', 10)
  },

  // Redis (optional, for rate limiting)
  redis: {
    enabled: process.env.REDIS_ENABLED === 'true',
    host: process.env.REDIS_HOST || 'localhost',
    port: parseInt(process.env.REDIS_PORT || '6379', 10),
    password: process.env.REDIS_PASSWORD || ''
  },

  // Rate Limiting
  rateLimit: {
    windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS || '60000', 10), // 1 minute
    maxRequests: parseInt(process.env.RATE_LIMIT_MAX_REQUESTS || '100', 10),
    skipSuccessfulRequests: false
  },

  // CORS
  cors: {
    origin: (function() {
      const origins = process.env.CORS_ALLOWED_ORIGINS;
      if (!origins) {
        // In development, allow all; in production, deny all if not configured
        return process.env.NODE_ENV === 'production' ? false : '*';
      }
      return origins.split(',').map(o => o.trim()).filter(Boolean);
    })(),
    credentials: true,
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization', 'X-API-Key']
  },

  // WebSocket
  websocket: {
    enabled: true,
    broadcastInterval: parseInt(process.env.WS_BROADCAST_INTERVAL || '30000', 10), // 30 seconds
    pingInterval: parseInt(process.env.WS_PING_INTERVAL || '25000', 10),
    pingTimeout: parseInt(process.env.WS_PING_TIMEOUT || '60000', 10)
  },

  // Logging
  logging: {
    level: process.env.LOG_LEVEL || 'info',
    lokiUrl: process.env.LOKI_URL || null
  },

  // Security
  security: {
    jwtSecret: process.env.JWT_SECRET,
    apiKey: process.env.API_KEY,
    jwtExpiresIn: process.env.JWT_EXPIRES_IN || '24h',
    bcryptRounds: parseInt(process.env.BCRYPT_ROUNDS || '10', 10)
  },

  // Cache
  cache: {
    ttl: parseInt(process.env.CACHE_TTL || '600', 10), // 10 minutes
    checkPeriod: parseInt(process.env.CACHE_CHECK_PERIOD || '120', 10) // 2 minutes
  }
};

// Validate configuration
function validateConfig() {
  const errors = [];

  if (config.app.port < 1024 || config.app.port > 65535) {
    errors.push('PORT must be between 1024 and 65535');
  }

  if (!config.services.claudeEngine.url.startsWith('http')) {
    errors.push('CLAUDE_ENGINE_URL must start with http:// or https://');
  }

  if (config.services.claudeEngine.timeout < 1000) {
    errors.push('CLAUDE_ENGINE_TIMEOUT must be at least 1000ms');
  }

  if (errors.length > 0) {
    console.error('Configuration validation errors:');
    errors.forEach(error => console.error(`  - ${error}`));
    process.exit(1);
  }
}

validateConfig();

// Production-specific security validation
if (config.app.env === 'production') {
  if (!process.env.JWT_SECRET || process.env.JWT_SECRET.length < 32) {
    console.error('FATAL: JWT_SECRET must be at least 32 characters in production');
    process.exit(1);
  }
  if (!process.env.API_KEY) {
    console.error('FATAL: API_KEY environment variable is required in production');
    process.exit(1);
  }
}

module.exports = config;
