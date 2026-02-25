/**
 * Winston Logger Configuration for API Gateway
 * Includes console and Loki transports for centralized logging
 */

const winston = require('winston');
const LokiTransport = require('winston-loki');

const { format } = winston;

// Custom format for pretty console output
const consoleFormat = format.combine(
  format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
  format.colorize(),
  format.printf(({ timestamp, level, message, service, ...meta }) => {
    let msg = `${timestamp} [${level}] [${service || 'api-gateway'}]: ${message}`;
    
    // Add metadata if present
    if (Object.keys(meta).length > 0) {
      msg += ` ${JSON.stringify(meta)}`;
    }
    
    return msg;
  })
);

// JSON format for Loki
const jsonFormat = format.combine(
  format.timestamp(),
  format.errors({ stack: true }),
  format.json()
);

// Create transports array
const transports = [
  // Console transport (always enabled)
  new winston.transports.Console({
    format: consoleFormat,
    level: process.env.LOG_LEVEL || 'info'
  })
];

// Add Loki transport if URL is configured
if (process.env.LOKI_URL) {
  transports.push(
    new LokiTransport({
      host: process.env.LOKI_URL,
      labels: {
        service: 'claude-trader-api-gateway',
        environment: process.env.NODE_ENV || 'development'
      },
      format: jsonFormat,
      level: 'info',
      batching: true,
      interval: 5
    })
  );
}

// Create logger instance
const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  defaultMeta: {
    service: 'claude-trader-api-gateway',
    environment: process.env.NODE_ENV || 'development'
  },
  transports
});

// Add stream for Morgan HTTP logger
logger.stream = {
  write: (message) => {
    logger.info(message.trim());
  }
};

module.exports = logger;
