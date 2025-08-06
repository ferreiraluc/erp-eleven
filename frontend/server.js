import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import { existsSync } from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const port = process.env.PORT || 3000;

const distPath = path.join(__dirname, 'dist');
const indexPath = path.join(distPath, 'index.html');

console.log('Server starting...');
console.log('Dist path:', distPath);
console.log('Index.html exists:', existsSync(indexPath));
console.log('Environment:', process.env.NODE_ENV || 'development');
console.log('API URL:', process.env.VITE_API_BASE_URL || 'Not configured');

// Serve static files from the dist directory
app.use(express.static(distPath, {
  setHeaders: (res, path) => {
    if (path.endsWith('.html')) {
      res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
    }
  }
}));

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ 
    status: 'ok', 
    timestamp: new Date().toISOString(),
    distExists: existsSync(distPath),
    indexExists: existsSync(indexPath)
  });
});

// Handle SPA routing - serve index.html for all non-API routes
app.get('*', (req, res) => {
  console.log('Serving SPA route:', req.path);
  if (existsSync(indexPath)) {
    res.sendFile(indexPath);
  } else {
    res.status(404).send('index.html not found');
  }
});

app.listen(port, '0.0.0.0', () => {
  console.log(`Frontend server running on port ${port}`);
  console.log(`Health check: http://localhost:${port}/health`);
});