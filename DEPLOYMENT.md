# ERP Eleven - Render Deployment Guide

## 🚀 How to Deploy to Render

### Prerequisites
1. GitHub account
2. Render account (free tier available)
3. Your project pushed to GitHub

### Step 1: Push Your Code to GitHub

```bash
# Initialize git repository (if not already done)
git init
git add .
git commit -m "Initial commit: ERP Eleven system"

# Add your GitHub repository
git remote add origin https://github.com/YOUR_USERNAME/erp-eleven.git
git push -u origin main
```

### Step 2: Deploy on Render

#### Option A: Using render.yaml (Recommended)

1. **Push render.yaml**: Make sure the `render.yaml` file is in your repository root
2. **Connect Repository**: 
   - Go to [render.com](https://render.com)
   - Click "New" → "Blueprint"
   - Connect your GitHub repository
   - Render will automatically detect the `render.yaml` file

#### Option B: Manual Setup

**1. Create PostgreSQL Database:**
- Go to Render Dashboard
- Click "New" → "PostgreSQL"
- Name: `erp-eleven-db`
- Plan: Free
- Note the connection details

**2. Deploy Backend:**
- Click "New" → "Web Service"
- Connect your GitHub repo
- Settings:
  - **Name**: `erp-eleven-backend`
  - **Environment**: Python 3
  - **Build Command**: `cd backend && pip install -r requirements.txt`
  - **Start Command**: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  - **Environment Variables**:
    ```
    DATABASE_URL = [PostgreSQL connection string from step 1]
    SECRET_KEY = your-secret-key-here
    ALGORITHM = HS256
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    ```

**3. Deploy Frontend:**
- Click "New" → "Static Site"
- Connect your GitHub repo
- Settings:
  - **Name**: `erp-eleven-frontend`
  - **Build Command**: `cd frontend && npm install && npm run build`
  - **Publish Directory**: `frontend/build`
  - **Environment Variables**:
    ```
    REACT_APP_API_URL = https://erp-eleven-backend.onrender.com
    ```

### Step 3: Initialize Database

After deployment, you need to create the database tables:

1. **Connect to your PostgreSQL database** using the connection details from Render
2. **Run the SQL schema** from `postgres.sql`:

```bash
# Using psql (if installed locally)
psql "postgresql://username:password@hostname:port/database" -f postgres.sql

# Or use pgAdmin, DBeaver, or any PostgreSQL client
```

### Step 4: Access Your Application

Once deployed, you'll have:
- **Frontend**: `https://erp-eleven-frontend.onrender.com`
- **Backend API**: `https://erp-eleven-backend.onrender.com`
- **Database**: PostgreSQL instance on Render

## 🛠 Local Development

### Frontend (React)
```bash
cd frontend
npm install
npm start
# Access: http://localhost:3000
```

### Backend (FastAPI)
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
# Access: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Database
- **Local**: PostgreSQL running on localhost:5432
- **Database**: eleven
- **User**: postgres
- **Password**: postgres

## 🔧 Environment Variables

### Backend (.env)
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/eleven
SECRET_KEY=your-secret-key-change-this
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### Frontend (.env)
```env
REACT_APP_API_URL=http://localhost:8000
```

## 📊 Monitoring

- **Render Dashboard**: Monitor deployments, logs, and metrics
- **API Health**: Check `https://your-backend.onrender.com/health`
- **Database**: Monitor connection and performance in Render dashboard

## 🐛 Troubleshooting

### Common Issues:

1. **Database Connection Failed**
   - Check DATABASE_URL format
   - Ensure PostgreSQL service is running
   - Verify credentials

2. **Frontend Can't Connect to API**
   - Check REACT_APP_API_URL is correct
   - Verify backend is deployed and running
   - Check CORS settings in backend

3. **Build Failures**
   - Check build commands in render.yaml
   - Verify all dependencies are in requirements.txt/package.json
   - Check logs in Render dashboard

### Render Free Tier Limitations:
- Services sleep after 15 minutes of inactivity
- 750 hours/month usage limit
- Database: 1 GB storage, 1 month retention

## 🔄 Updates and Maintenance

To update your deployed application:
1. Push changes to your GitHub repository
2. Render will automatically redeploy (if auto-deploy is enabled)
3. For database changes, run migrations manually

## 📚 Additional Resources

- [Render Documentation](https://render.com/docs)
- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)
- [React Deployment Guide](https://create-react-app.dev/docs/deployment/)