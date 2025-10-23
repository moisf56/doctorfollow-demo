# Vercel Deployment Guide - Connect Frontend to Render Backend

## 🎯 Overview

Your backend is now live on Render! This guide will help you:
1. Configure your React frontend to connect to Render backend
2. Deploy to Vercel
3. Set up CORS properly
4. Test the connection

---

## 📋 Prerequisites

- ✅ Backend deployed on Render (running)
- ✅ Frontend React app ready (`doctor-follow-app`)
- ✅ Vercel account (free tier works)
- ✅ Git repository

---

## Step 1: Get Your Render Backend URL

Your Render backend URL should look like:
```
https://doctorfollow-api.onrender.com
```

**To find it:**
1. Go to Render Dashboard
2. Click on your service (`doctorfollow-api`)
3. Copy the URL at the top (e.g., `https://doctorfollow-api-xxxx.onrender.com`)

---

## Step 2: Update Backend CORS Settings

Your backend needs to allow requests from your Vercel frontend.

### A. Update `api_server.py` CORS Configuration

Edit: `testing/iteration_3/api_server.py`

Find the CORS origins section (around line 60-65):

```python
# Current (localhost only)
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
]

# Update to (add your Vercel URL)
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://your-app-name.vercel.app",  # Add your Vercel URL here
    "https://*.vercel.app",  # Allow all Vercel preview deployments
]
```

**Or use environment variable** (recommended):

```python
# Better approach - use environment variable
import os

allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",")]
```

### B. Add ALLOWED_ORIGINS to Render Environment Variables

1. Go to Render Dashboard → Your Service → Environment
2. Add variable:
   ```
   Key: ALLOWED_ORIGINS
   Value: http://localhost:3000,https://your-app-name.vercel.app,https://*.vercel.app
   ```
3. Save and redeploy

---

## Step 3: Prepare Frontend for Deployment

### A. Create `.env.production` File

In `testing/frontend/doctor-follow-app/`:

```bash
# .env.production
REACT_APP_API_URL=https://doctorfollow-api.onrender.com
```

Replace `doctorfollow-api.onrender.com` with your actual Render URL.

### B. Update `.env` for Local Development

```bash
# .env (for local testing)
REACT_APP_API_URL=http://localhost:8000
```

### C. Create `vercel.json` Configuration

In `testing/frontend/doctor-follow-app/vercel.json`:

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "build",
  "devCommand": "npm start",
  "installCommand": "npm install",
  "framework": "create-react-app",
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "X-Content-Type-Options",
          "value": "nosniff"
        },
        {
          "key": "X-Frame-Options",
          "value": "DENY"
        },
        {
          "key": "X-XSS-Protection",
          "value": "1; mode=block"
        }
      ]
    }
  ],
  "env": {
    "REACT_APP_API_URL": "@react_app_api_url"
  }
}
```

---

## Step 4: Deploy to Vercel

### Option 1: Deploy via Vercel CLI

```bash
# 1. Install Vercel CLI (if not installed)
npm install -g vercel

# 2. Navigate to frontend directory
cd testing/frontend/doctor-follow-app

# 3. Login to Vercel
vercel login

# 4. Deploy
vercel

# Follow prompts:
# - Set up and deploy? Yes
# - Which scope? (your account)
# - Link to existing project? No
# - Project name: doctorfollow-frontend
# - Directory: ./
# - Override settings? No

# 5. Deploy to production
vercel --prod
```

### Option 2: Deploy via Vercel Dashboard

1. **Push to GitHub**
   ```bash
   cd testing/frontend/doctor-follow-app
   git init
   git add .
   git commit -m "Initial frontend commit"
   git remote add origin <your-github-repo-url>
   git push -u origin main
   ```

2. **Connect to Vercel**
   - Go to https://vercel.com/
   - Click "Add New Project"
   - Import your GitHub repository
   - Select `testing/frontend/doctor-follow-app` as root directory

3. **Configure Build Settings**
   - Framework Preset: `Create React App`
   - Build Command: `npm run build`
   - Output Directory: `build`
   - Install Command: `npm install`

4. **Add Environment Variables**
   - Go to Settings → Environment Variables
   - Add:
     ```
     Key: REACT_APP_API_URL
     Value: https://doctorfollow-api.onrender.com
     ```
   - Apply to: Production, Preview, Development

5. **Deploy**
   - Click "Deploy"
   - Wait for build to complete (~2-3 minutes)

---

## Step 5: Update Backend with Vercel URL

After Vercel deployment completes:

1. **Get your Vercel URL**
   ```
   https://doctorfollow-frontend.vercel.app
   ```

2. **Update Render Environment Variables**
   - Go to Render Dashboard
   - Update `ALLOWED_ORIGINS`:
     ```
     http://localhost:3000,https://doctorfollow-frontend.vercel.app
     ```
   - Save and redeploy

---

## Step 6: Test the Connection

### A. Test Backend Health

```bash
curl https://doctorfollow-api.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-23T..."
}
```

### B. Test Frontend → Backend Connection

1. Open your Vercel URL: `https://doctorfollow-frontend.vercel.app`
2. You should see the login page
3. Enter credentials:
   - Username: `demo`
   - Password: (from your Render env vars `DEMO_PASSWORD`)
4. Try asking a question: "What is RDS treatment?"
5. Check browser console for any errors (F12 → Console)

---

## Step 7: Troubleshooting

### Issue: CORS Error

**Symptom:**
```
Access to fetch at 'https://...' has been blocked by CORS policy
```

**Fix:**
1. Check backend `ALLOWED_ORIGINS` includes your Vercel URL
2. Restart Render service after updating env vars
3. Clear browser cache (Ctrl+Shift+Delete)

### Issue: 401 Unauthorized

**Symptom:**
```
Failed to fetch / 401 Unauthorized
```

**Fix:**
1. Check `DEMO_USERNAME` and `DEMO_PASSWORD` in Render env vars
2. Verify credentials match what you're entering
3. Check browser console for auth header

### Issue: Connection Refused / Timeout

**Symptom:**
```
Failed to fetch: Connection refused
```

**Fix:**
1. Verify Render service is running (Dashboard → Service → Logs)
2. Check backend URL is correct (no typos)
3. Try accessing backend health endpoint directly

### Issue: Slow First Request

**Symptom:**
First request takes 30+ seconds

**Explanation:**
Render free tier "spins down" after 15 minutes of inactivity. First request wakes it up.

**Solutions:**
- Upgrade to Render paid tier ($7/month, always running)
- Use a monitoring service to ping every 14 minutes
- Accept the initial delay (only affects first request)

---

## Step 8: Optional - Set Up Custom Domain

### For Frontend (Vercel)

1. Go to Vercel Dashboard → Your Project → Settings → Domains
2. Add your custom domain (e.g., `doctorfollow.com`)
3. Update DNS records as instructed by Vercel
4. Update backend `ALLOWED_ORIGINS` to include custom domain

### For Backend (Render)

1. Go to Render Dashboard → Your Service → Settings
2. Add custom domain (e.g., `api.doctorfollow.com`)
3. Update DNS records as instructed by Render
4. Update frontend `REACT_APP_API_URL` in Vercel env vars

---

## 📁 Final Project Structure

```
doctorfollow-demo/
├── testing/
│   ├── frontend/
│   │   └── doctor-follow-app/
│   │       ├── .env                    # Local development
│   │       ├── .env.production         # Production config
│   │       ├── vercel.json            # Vercel config
│   │       ├── src/
│   │       │   └── App.js             # Already configured!
│   │       └── package.json
│   ├── iteration_3/
│   │   └── api_server.py              # Update CORS
│   └── render.yaml                     # Backend deployment
```

---

## 🚀 Quick Start Checklist

- [ ] Get Render backend URL
- [ ] Update backend CORS (`ALLOWED_ORIGINS`)
- [ ] Create `.env.production` with Render URL
- [ ] Create `vercel.json` config
- [ ] Deploy to Vercel (CLI or Dashboard)
- [ ] Update backend with Vercel URL
- [ ] Test login and chat functionality
- [ ] Monitor first-load performance

---

## 📊 Expected Performance

- **Backend cold start**: 15-30 seconds (first request after idle)
- **Backend warm**: 100-300ms per request
- **Frontend load**: 1-2 seconds
- **Chat streaming**: Real-time (50-100ms chunks)
- **Total first query**: ~2-5 seconds (includes Jina AI API call)

---

## 🔒 Security Checklist

- ✅ HTTPS enabled (automatic on Render + Vercel)
- ✅ HTTP Basic Auth for API
- ✅ CORS configured properly
- ✅ Session credentials in sessionStorage (not localStorage)
- ✅ Passwords not exposed in frontend code
- ✅ Environment variables used for secrets

---

## 💡 Next Steps

1. **Monitor Usage**
   - Render: Dashboard → Metrics
   - Vercel: Dashboard → Analytics

2. **Set Up Alerts**
   - Render: Add webhook for downtime alerts
   - Vercel: Enable deployment notifications

3. **Consider Upgrades**
   - Render Starter ($7/month) - no cold starts, better performance
   - Vercel Pro ($20/month) - better analytics, more build minutes

4. **Add Features**
   - User registration system
   - Conversation history persistence
   - File upload for custom PDFs
   - Admin dashboard

---

## 📞 Support

If you encounter issues:

1. **Check Logs**
   - Render: Dashboard → Logs tab
   - Vercel: Dashboard → Deployments → View Logs
   - Browser: F12 → Console

2. **Test Components Separately**
   - Backend health: `curl https://your-api.onrender.com/health`
   - Frontend local: `npm start` (with localhost backend)

3. **Common Commands**
   ```bash
   # Test backend locally
   cd testing/iteration_3
   python api_server.py

   # Test frontend locally
   cd testing/frontend/doctor-follow-app
   npm start

   # Deploy frontend to Vercel
   vercel --prod

   # View Vercel logs
   vercel logs
   ```

---

**Your app is ready to go live! 🎉**

Backend: `https://doctorfollow-api.onrender.com`
Frontend: `https://doctorfollow-frontend.vercel.app`
