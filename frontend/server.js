import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import { existsSync } from 'fs';
import compression from 'compression';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const port = parseInt(process.env.PORT, 10) || 3000;
const isProduction = process.env.NODE_ENV === 'production';

const distPath = path.join(__dirname, 'dist');
const indexPath = path.join(distPath, 'index.html');

// Only log in development
if (!isProduction) {
  console.log('Server starting...');
  console.log('Dist path:', distPath);
  console.log('Index.html exists:', existsSync(indexPath));
  console.log('Environment:', process.env.NODE_ENV || 'development');
}

// Production optimizations
if (isProduction) {
  // Compress responses
  app.use(compression());
  
  // Basic security headers (less restrictive)
  app.use((_req, res, next) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    // Removed X-Frame-Options and XSS-Protection for compatibility
    next();
  });
  
  // Disable powered by header
  app.disable('x-powered-by');
}

// Serve static files FIRST, before any other middleware
app.use(express.static(distPath));

// Add debug logging for non-static requests
app.use((req, res, next) => {
  console.log(`${new Date().toISOString()} - ${req.method} ${req.url}`);
  next();
});

// Health check endpoint
app.get('/health', (_req, res) => {
  res.json({ 
    status: 'ok', 
    timestamp: new Date().toISOString(),
    environment: process.env.NODE_ENV || 'development',
    distPath: distPath,
    distExists: existsSync(distPath),
    indexExists: existsSync(indexPath),
    apiUrl: process.env.VITE_API_BASE_URL || 'not set',
    user: process.env.USER || 'unknown',
    permissions: 'checking...'
  });
});

// Simplified debug endpoints
app.get('/debug/index', (_req, res) => {
  try {
    res.json({
      indexExists: existsSync(indexPath),
      indexPath: indexPath,
      message: 'Index file check'
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/debug/assets', (_req, res) => {
  const assetsPath = path.join(distPath, 'assets');
  try {
    const fs = require('fs');
    const files = existsSync(assetsPath) ? fs.readdirSync(assetsPath) : [];
    
    res.json({
      assetsPath: assetsPath,
      assetsExists: existsSync(assetsPath),
      distExists: existsSync(distPath),
      filesCount: files.length,
      firstFewFiles: files.slice(0, 5),
      message: 'Assets directory check with file list'
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Test serving a specific asset manually
app.get('/debug/test-js', (_req, res) => {
  try {
    const fs = require('fs');
    const assetsPath = path.join(distPath, 'assets');
    const files = fs.readdirSync(assetsPath);
    const jsFile = files.find(f => f.startsWith('index-') && f.endsWith('.js'));
    
    if (jsFile) {
      const jsPath = path.join(assetsPath, jsFile);
      const content = fs.readFileSync(jsPath, 'utf8');
      res.type('application/javascript').send(content.substring(0, 500) + '...[truncated]');
    } else {
      res.status(404).json({ error: 'No index JS file found', files });
    }
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Handle SPA routing - serve index.html for all non-API routes
app.get('*', (req, res) => {
  if (!isProduction) {
    console.log('Serving SPA route:', req.path);
  }
  
  if (existsSync(indexPath)) {
    res.sendFile(indexPath);
  } else {
    res.status(404).json({ error: 'Application not built. Run npm run build first.' });
  }
});

// Error handling middleware
app.use((err, _req, res, _next) => {
  if (!isProduction) {
    console.error('Server error:', err);
  }
  res.status(500).json({ error: 'Internal server error' });
});

const server = app.listen(port, '0.0.0.0', () => {
  console.log(`Frontend server running on port ${port}`);
  if (!isProduction) {
    console.log(`Health check: http://localhost:${port}/health`);
  }
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('SIGTERM received, shutting down gracefully...');
  server.close(() => {
    console.log('Process terminated');
    process.exit(0);
  });
});

process.on('SIGINT', () => {
  console.log('SIGINT received, shutting down gracefully...');
  server.close(() => {
    console.log('Process terminated');
    process.exit(0);
  });
});