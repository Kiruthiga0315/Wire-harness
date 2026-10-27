# Deployment Guide

This guide details deployment and operational procedures for the AI Wire Harness Final Inspection System. The stack consists of:
- **Backend**: FastAPI (Python 3.11+) with Uvicorn, SQLite/PostgreSQL, and OpenCV image processing pipelines.
- **Frontend**: Single-page application built with React 19, TypeScript, and Vite.
- **API Documentation**: Interactive Swagger UI (`/docs`) and ReDoc (`/redoc`) served directly by FastAPI.

---

## Architecture Overview

```text
+-----------------------------+
|    React 19 Frontend        |
|    (Vite / Static Host)     |
+--------------+--------------+
               | HTTP / REST API
               v
+-----------------------------+
|    FastAPI Backend          | <---> Swagger UI (/docs)
|    (Uvicorn ASGI Server)    | <---> ReDoc (/redoc)
+--------------+--------------+
               |
        +------+------+
        |             |
        v             v
   SQLite / PG     OpenCV Engine
   Database        (Vision & Topology)
```

---

## Local Development & Operations

### 1. Unified Launcher
Start both the backend and frontend together using `run.py`:

```bash
python run.py
```
Or on Windows:
```powershell
.\run.cmd
```

- **Frontend**: http://127.0.0.1:5173
- **Backend**: http://127.0.0.1:8000
- **Swagger Documentation**: http://127.0.0.1:8000/docs
- **Health Check**: http://127.0.0.1:8000/api/health

### 2. Independent Services

#### Backend Service
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Frontend Service
```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

---

## Production Deployment

### Option A: Containerized Deployment (Docker / Docker Compose)

The repository provides a `docker-compose.yml` for multi-service environments.

1. **Build and Run**:
```bash
docker compose up --build -d
```
2. **Access**:
- Frontend HMI: `http://<host>:5173` (or port `80` if mapped to reverse proxy)
- Backend API: `http://<host>:8000`
- Swagger UI: `http://<host>:8000/docs`

### Option B: Cloud Hosting (Render / Railway / VPS)

#### 1. Backend Web Service (Render / Railway / Cloud)
- **Root Directory**: (Leave blank / repository root)
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT` (or `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`)
- **Environment Variables**:
  - `PORT`: Configured automatically by host
  - `ENVIRONMENT`: `production`
  - `FRONTEND_URL`: `https://wire-harness-rho.vercel.app`
  - `DATABASE_URL`: `sqlite:///data/inspection.db` (or `postgresql+psycopg://user:pass@host:5432/db`)

#### 2. Frontend Static Site (Vercel / Netlify / Cloudflare Pages)
- **Framework Preset**: Vite
- **Root Directory**: `frontend`
- **Build Command**: `npm run build`
- **Output Directory**: `dist`
- **Environment Variables**:
  - `VITE_API_URL`: URL of the deployed backend (e.g. `https://api.yourdomain.com`)

---

## Verification & Health Monitoring

1. **Backend Health Check**:
   ```bash
   curl -s http://127.0.0.1:8000/api/health
   ```
   Expected response:
   ```json
   {
     "status": "healthy",
     "service": "wire-harness-inspection-api",
     "database": "connected",
     "version": "0.1.0"
   }
   ```

2. **OpenAPI Schema Check**:
   ```bash
   curl -s http://127.0.0.1:8000/openapi.json | head -n 10
   ```

3. **Automated Test Suite**:
   ```bash
   python -m pytest
   ```

4. **Frontend Production Build**:
   ```bash
   npm --prefix frontend run build
   ```
