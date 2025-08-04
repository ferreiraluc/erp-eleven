# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an ERP system project named "Eleven" for managing clothing store operations. The system handles sales, vendors, currency exchange, orders, and employee data with multi-currency support.

## Development Commands

### Backend (FastAPI + PostgreSQL)
```bash
# Setup backend environment
cd backend
source venv/bin/activate
pip install -r requirements.txt

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Database setup (ensure PostgreSQL is running)
# Database: eleven, User: postgres, Password: postgres
```

### Frontend (React + TypeScript)
```bash
# Setup frontend
cd frontend
npm install

# Start development server
npm start

# Build for production
npm run build

# Run tests
npm test
```

### Database Configuration
- **Database**: PostgreSQL
- **Database Name**: eleven
- **Username**: postgres
- **Password**: postgres
- **Port**: 5432
- **Schema**: Already created via postgres.sql

## Architecture

### Backend Structure (FastAPI)
- **Models**: SQLAlchemy models matching PostgreSQL schema
- **Schemas**: Pydantic models for API serialization
- **Endpoints**: RESTful API routes for each entity
- **Database**: PostgreSQL with comprehensive ERP schema

### Frontend Structure (React TypeScript)
- **Framework**: React 19 with TypeScript
- **Routing**: React Router DOM
- **HTTP Client**: Axios
- **Styling**: Tailwind CSS
- **State Management**: React hooks

## Core Entities

- **Vendas (Sales)**: Multi-currency sales tracking with commission calculations
- **Vendedores (Vendors)**: Vendor management with performance metrics
- **Cambistas (Currency Exchangers)**: Exchange rate management for G$, R$, U$, EUR
- **Comprovantes (Receipts)**: Document management and approval workflow
- **Pedidos (Orders)**: Order processing and logistics management
- **Funcionarios (Employees)**: HR management with scheduling

## API Endpoints

Current available endpoints:
- GET/POST `/api/vendedores` - Vendor management
- GET/POST `/api/cambistas` - Currency exchanger management  
- GET/POST `/api/vendas` - Sales management
- GET `/health` - Health check
- GET `/` - API root

## Key Features

- Multi-currency support (G$, R$, U$, EUR)
- Commission-based vendor compensation
- Document approval workflows
- Order tracking with shipping integration
- Employee scheduling and payroll management
- Weekly commission closing system