# TwinOps Free Cloud Deployment Guide

This guide explains how to deploy the entire **TwinOps Digital Twin Platform** (all 7 microservices, live plant simulator, WebSockets, and the React-Three-Fiber 3D UI) **100% for free** using modern cloud hosting platforms.

---

## 1. Where Can You Deploy for Free?

| Platform | Free Plan Specs | Best For | Deploy Method |
| :--- | :--- | :--- | :--- |
| **Render.com** *(Recommended)* | 512 MB RAM, 0.1 CPU, Free SSL, Public Domain | Web app demo + API + WebSocket | GitHub Integration / `render.yaml` |
| **Hugging Face Spaces** | **16 GB RAM**, **2 vCPUs**, Free public URL | Heavy AI/ML + 3D Twin Demos | Docker Space |
| **Koyeb** | 512 MB RAM, 0.1 CPU, Global Edge CDN | Global low-latency API & Web | Docker / Git Push |
| **Fly.io** | 256–512 MB RAM allowance, Anycast IP | MicroVM container deployment | `fly launch` (CLI) |
| **Vercel / Cloudflare Pages** | Unlimited bandwidth, Global Edge | Frontend Only (`web/`) | Git Push |

---

## 2. How the Unified Deployment Works

In local development, TwinOps runs each microservice on dedicated ports (`8001` through `8007`).
For free cloud hosting—where free tiers usually allow **one web service instance**—TwinOps provides a **Unified Gateway (`services/gateway.py`)**:

- Mounts all 7 microservice domains under `/api/v1/`
- Serves the live WebSocket channel at `/ws/live?site=PUNE-01`
- Runs the virtual plant simulator in the background (generating continuous live telemetry)
- Serves the compiled production React-Three-Fiber 3D frontend (`web/dist`) directly from the root `/`

**The entire system runs inside a single lightweight container on Port 8000!**

---

## 3. Step-by-Step Deployment Instructions

### Option A: Render.com (Recommended — 3 Minutes)

1. Push this repository to your **GitHub** account.
2. Sign up / Log in to [Render.com](https://render.com) (free account).
3. Click **New +** → **Web Service**.
4. Connect your GitHub repository.
5. Configure the service:
   - **Name**: `twinops-digital-twin`
   - **Environment**: `Docker`
   - **Region**: Choose closest to you (e.g. Frankfurt, Oregon, Singapore)
   - **Branch**: `master` (or `main`)
   - **Plan**: `Free`
6. Click **Create Web Service**.
7. Render will automatically build the multi-stage Dockerfile and assign you a live HTTPS URL:
   `https://twinops-digital-twin.onrender.com`

---

### Option B: Hugging Face Spaces (Most Powerful Free Tier: 16GB RAM)

Hugging Face Spaces offers **16 GB RAM and 2 vCPUs completely free** with no credit card required:

1. Sign up / Log in to [Hugging Face](https://huggingface.co).
2. Go to **Spaces** → **Create new Space**.
3. Configure your Space:
   - **Space Name**: `twinops-plant-twin`
   - **License**: `MIT` or `Apache 2.0`
   - **Space SDK**: Choose **Docker** → **Blank**.
   - **Space Hardware**: Free (CPU basic · 2 vCPU · 16 GB).
4. Clone the space repo or push your files:
   ```bash
   git remote add hf https://huggingface.co/spaces/<your-username>/twinops-plant-twin
   git push hf master
   ```
5. Hugging Face will automatically build the Dockerfile and present the full 3D interactive digital twin live at:
   `https://huggingface.co/spaces/<your-username>/twinops-plant-twin`

---

### Option C: Koyeb (Fast Global Edge Deployment)

1. Sign up at [Koyeb.com](https://www.koyeb.com).
2. Click **Create App** → **GitHub**.
3. Select this repository.
4. Set **Builder** to `Dockerfile`.
5. Under **Ports**, set internal port to `8000` (HTTP).
6. Click **Deploy**. Your app will be live with free global CDN and SSL.

---

### Option D: Local Docker (Self-Hosted on Any Server)

You can also run the unified container anywhere Docker is installed (your own laptop, Raspberry Pi, or local server):

```bash
# 1. Build the production image
docker build -t twinops:latest .

# 2. Run the container
docker run -d -p 8000:8000 --name twinops twinops:latest

# 3. Open your browser
# Navigate to: http://localhost:8000
```

---

## 4. Verifying the Cloud Deployment

Once deployed, verify your public URL:
- **3D Digital Twin Viewer**: `https://<your-app-domain>/`
- **Dashboard & KPIs**: `https://<your-app-domain>/#/`
- **Asset Library**: `https://<your-app-domain>/#/assets`
- **Predictive Insights**: `https://<your-app-domain>/#/insights`
- **Health Check**: `https://<your-app-domain>/healthz`
- **Live WebSocket**: `wss://<your-app-domain>/ws/live?site=PUNE-01`
- **AI Copilot API**: `POST https://<your-app-domain>/api/v1/copilot/chat`
