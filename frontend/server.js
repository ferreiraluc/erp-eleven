import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import { existsSync } from 'fs';
import compression from 'compression';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const port = process.env.PORT || 3000;
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
  
  // Security headers
  app.use((_req, res, next) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('X-Frame-Options', 'DENY');
    res.setHeader('X-XSS-Protection', '1; mode=block');
    res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
    next();
  });
  
  // Disable powered by header
  app.disable('x-powered-by');
}

// Serve static files from the dist directory
app.use(express.static(distPath, {
  maxAge: isProduction ? '1y' : '0', // Cache static assets for 1 year in production
  setHeaders: (res, filePath) => {
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
  res.json({ 
    status: 'ok', 
    timestamp: new Date().toISOString(),
    environment: process.env.NODE_ENV || 'development',
    distExists: existsSync(distPath),
    indexExists: existsSync(indexPath)
  });
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

app.listen(port, '0.0.0.0', () => {
  console.log(`Frontend server running on port ${port}`);
  if (!isProduction) {
    console.log(`Health check: http://localhost:${port}/health`);
  }
});