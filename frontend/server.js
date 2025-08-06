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

// Add debug logging for all requests
app.use((req, res, next) => {
  console.log(`${new Date().toISOString()} - ${req.method} ${req.url}`);
  next();
});

// Serve static files from the dist directory
app.use(express.static(distPath, {
  index: false, // Disable automatic serving of index.html
  maxAge: isProduction ? '1y' : '0',
  setHeaders: (res, filePath) => {
    console.log(`Serving static file: ${filePath}`);
    // No cache for HTML files
    if (filePath.endsWith('.html')) {
      res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
      res.setHeader('Pragma', 'no-cache');
      res.setHeader('Expires', '0');
    }
    // Long cache for JS/CSS with hash in filename
    else if (/\.(js|css)$/.test(filePath) && /-[a-f0-9]{8}\./.test(filePath)) {
      res.setHeader('Cache-Control', 'public, max-age=31536000, immutable');
    }
  }
}));

// Health check endpoint
app.get('/health', (_req, res) => {
  const fs = require('fs');
  let distContents = [];
  let assetsContents = [];
  let indexSize = 0;
  let indexContent = '';
  
  try {
    if (existsSync(distPath)) {
      distContents = fs.readdirSync(distPath);
      const assetsPath = path.join(distPath, 'assets');
      if (existsSync(assetsPath)) {
        assetsContents = fs.readdirSync(assetsPath);
      }
    }
    if (existsSync(indexPath)) {
      const stats = fs.statSync(indexPath);
      indexSize = stats.size;
      indexContent = fs.readFileSync(indexPath, 'utf8').substring(0, 500); // First 500 chars
    }
  } catch (err) {
    console.error('Error reading dist directory:', err);
  }

  res.json({ 
    status: 'ok', 
    timestamp: new Date().toISOString(),
    environment: process.env.NODE_ENV || 'development',
    distPath: distPath,
    distExists: existsSync(distPath),
    indexExists: existsSync(indexPath),
    indexSize: indexSize,
    indexPreview: indexContent,
    distContents: distContents,
    assetsContents: assetsContents,
    apiUrl: process.env.VITE_API_BASE_URL || 'not set'
  });
});

// Debug endpoint to see raw index.html
app.get('/debug/index', (_req, res) => {
  const fs = require('fs');
  try {
    if (existsSync(indexPath)) {
      const content = fs.readFileSync(indexPath, 'utf8');
      res.type('text/plain').send(content);
    } else {
      res.status(404).send('Index file not found');
    }
  } catch (err) {
    res.status(500).send('Error reading index file: ' + err.message);
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