# Frontend Dockerfile for production deployment
FROM node:22-alpine AS builder

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies (including dev dependencies for build)
RUN npm install

# Copy source code and configuration files
COPY . .

# Debug: Show what files we have before build
RUN ls -la

# Build the application
RUN NODE_ENV=production npm run build

# Debug: Show what was built
RUN ls -la dist/

# Production stage
FROM node:22-alpine AS production

# Install curl for health checks
RUN apk add --no-cache curl

WORKDIR /app

# Copy package files for server dependencies
COPY package*.json ./

# Install only production dependencies
RUN npm install --only=production

# Copy built application from builder stage
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/server.js ./server.js

# Debug: Verify files are copied and check permissions
RUN ls -la && ls -la dist/ && ls -la dist/assets/

# Create non-root user for security
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001

# Change ownership and permissions of the app directory
RUN chown -R nextjs:nodejs /app && \
    chmod -R 755 /app && \
    chmod -R 644 /app/dist/* && \
    chmod 755 /app/dist /app/dist/assets

USER nextjs

# Expose port
EXPOSE 3000

# Health check using curl instead of wget
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

# Start the server
CMD ["node", "server.js"]