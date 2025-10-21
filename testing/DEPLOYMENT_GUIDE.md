# DoctorFollow Deployment Guide

Complete guide to deploy your Medical RAG application with authentication to the internet for free (or low cost).

---

## 🎯 Deployment Overview

**Architecture:**
- **Frontend (React)**: Deployed on Vercel (FREE)
- **Backend (FastAPI)**: Deployed on Render (750 hrs/month FREE)
- **Database (PostgreSQL + pgvector)**: Render PostgreSQL (90 days FREE, then $7/month)
- **Neo4j**: Neo4j Aura Free Tier (FREE forever)
- **OpenAI API**: Your existing key (pay-per-use)

**Total Cost:**
- First 2-3 months: **$0**
- After free tier: **~$7-15/month**

---

## 📋 Prerequisites

Before deployment, make sure you have:

1. ✅ GitHub account (for code hosting)
2. ✅ Vercel account (sign up at https://vercel.com - FREE)
3. ✅ Render account (sign up at https://render.com - FREE)
4. ✅ Neo4j Aura account (sign up at https://neo4j.com/cloud/aura - FREE)
5. ✅ OpenAI API key (you already have this)
6. ✅ Your DoctorFollow code pushed to GitHub

---

## 🚀 Deployment Steps

### Step 1: Prepare Your Code for Deployment

#### 1.1 Update Environment Variables

Create `testing/.env.production` with your production credentials:

```bash
# Authentication
DEMO_USERNAME=demo
DEMO_PASSWORD=YourSecurePassword2025!

# CORS (will update after frontend deployment)
ALLOWED_ORIGINS=https://your-app.vercel.app

# LLM Provider
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-actual-key-here
OPENAI_MODEL=gpt-4o-mini

# Databases (will get from Render)
POSTGRES_HOST=your-render-postgres-host
POSTGRES_PORT=5432
POSTGRES_DB=doctorfollow
POSTGRES_USER=doctorfollow
POSTGRES_PASSWORD=your-secure-db-password

# Neo4j (will get from Neo4j Aura)
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-neo4j-password

# Embedding Model
EMBEDDING_MODEL=intfloat/multilingual-e5-large
EMBEDDING_DIMENSION=1024
```

#### 1.2 Create Frontend Environment File

Create `testing/frontend/doctor-follow-app/.env.production`:

```bash
REACT_APP_API_URL=https://your-backend.onrender.com
```

#### 1.3 Update Frontend API URL

The frontend needs to point to your deployed backend. We'll update this after getting the Render URL.

---

### Step 2: Deploy Neo4j Knowledge Graph (FREE)

1. Go to https://neo4j.com/cloud/aura
2. Click "Start Free"
3. Create a new **AuraDB Free** instance:
   - Name: `doctorfollow-kg`
   - Region: Choose closest to you
4. **IMPORTANT**: Save the connection details:
   - URI: `neo4j+s://xxxxx.databases.neo4j.io`
   - Username: `neo4j`
   - Password: (save this - shown only once!)
5. Update your `.env.production` with these details

---

### Step 3: Deploy PostgreSQL Database (FREE for 90 days)

1. Go to https://render.com
2. Click "New +" → "PostgreSQL"
3. Configure:
   - Name: `doctorfollow-db`
   - Database: `doctorfollow`
   - User: `doctorfollow`
   - Region: Choose closest to you
   - Plan: **Free** (90 days free, then $7/month)
4. Click "Create Database"
5. Wait for provisioning (~2 minutes)
6. Get connection details:
   - Internal Database URL: (use this in your backend)
   - Hostname, Port, Database, Username, Password
7. Update your `.env.production`

#### 3.1 Enable pgvector Extension

Connect to your Render PostgreSQL and run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

You can do this from Render dashboard → "Shell" tab.

---

### Step 4: Deploy Backend (FastAPI) to Render (FREE 750 hrs/month)

#### 4.1 Create `render.yaml` in `testing/` folder

This file tells Render how to deploy your app:

```yaml
services:
  - type: web
    name: doctorfollow-api
    env: python
    region: oregon
    plan: free
    buildCommand: |
      cd iteration_3
      pip install -r ../requirements.txt
      python -m spacy download en_core_web_sm
    startCommand: |
      cd iteration_3
      python api_server.py
    envVars:
      - key: DEMO_USERNAME
        value: demo
      - key: DEMO_PASSWORD
        generateValue: true
      - key: ALLOWED_ORIGINS
        value: https://your-frontend.vercel.app
      - key: LLM_PROVIDER
        value: openai
      - key: OPENAI_API_KEY
        sync: false
      - key: OPENAI_MODEL
        value: gpt-4o-mini
      - key: POSTGRES_HOST
        fromDatabase:
          name: doctorfollow-db
          property: host
      - key: POSTGRES_PORT
        fromDatabase:
          name: doctorfollow-db
          property: port
      - key: POSTGRES_DB
        fromDatabase:
          name: doctorfollow-db
          property: database
      - key: POSTGRES_USER
        fromDatabase:
          name: doctorfollow-db
          property: user
      - key: POSTGRES_PASSWORD
        fromDatabase:
          name: doctorfollow-db
          property: password
      - key: NEO4J_URI
        sync: false
      - key: NEO4J_USER
        value: neo4j
      - key: NEO4J_PASSWORD
        sync: false
      - key: EMBEDDING_MODEL
        value: intfloat/multilingual-e5-large
      - key: EMBEDDING_DIMENSION
        value: 1024
```

#### 4.2 Deploy to Render

1. Push your code to GitHub (including `render.yaml`)
2. Go to https://render.com dashboard
3. Click "New +" → "Web Service"
4. Connect your GitHub repository
5. Select the `DoctorFollow-Minimal-Demo` repository
6. Render will detect `render.yaml` automatically
7. Click "Apply"
8. Add secret environment variables manually:
   - `OPENAI_API_KEY`: Your OpenAI key
   - `NEO4J_URI`: From Neo4j Aura
   - `NEO4J_PASSWORD`: From Neo4j Aura
   - `DEMO_PASSWORD`: Your chosen demo password
9. Click "Create Web Service"
10. Wait for deployment (~5-10 minutes first time)
11. Your API will be live at: `https://doctorfollow-api.onrender.com`

**Note**: Free tier spins down after 15 minutes of inactivity. First request after idle takes ~30 seconds to wake up.

---

### Step 5: Deploy Frontend (React) to Vercel (FREE forever)

#### 5.1 Update Frontend to Use Production API

Edit `testing/frontend/doctor-follow-app/src/App_with_auth.js`:

Find all instances of `http://localhost:8000` and replace with:

```javascript
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Then use API_URL in fetch calls:
fetch(`${API_URL}/auth/login`, {
  // ...
})

fetch(`${API_URL}/chat/stream`, {
  // ...
})
```

#### 5.2 Create `vercel.json` Configuration

Create `testing/frontend/doctor-follow-app/vercel.json`:

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "build",
  "devCommand": "npm start",
  "framework": "create-react-app",
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "/"
    }
  ]
}
```

#### 5.3 Deploy to Vercel

1. Push your updated frontend code to GitHub
2. Go to https://vercel.com
3. Click "New Project"
4. Import your GitHub repository
5. Select `testing/frontend/doctor-follow-app` as root directory
6. Framework Preset: **Create React App**
7. Add Environment Variable:
   - `REACT_APP_API_URL`: `https://doctorfollow-api.onrender.com`
8. Click "Deploy"
9. Wait 2-3 minutes
10. Your app is live at: `https://your-app.vercel.app`

---

### Step 6: Update CORS Settings

Now that you have your frontend URL, update backend CORS:

1. Go to Render dashboard → Your web service
2. Environment tab
3. Update `ALLOWED_ORIGINS`:
   ```
   https://your-app.vercel.app,http://localhost:3000
   ```
4. Save changes
5. Render will redeploy automatically

---

### Step 7: Initialize Database

You need to upload your medical documents and build the knowledge graph.

#### 7.1 Run Data Ingestion Script

From your local machine (with access to your PDF):

```bash
cd testing/iteration_3

# Update .env to point to production databases
# Then run ingestion
python medical_kg_builder.py
```

This will:
- Extract text from Nelson-essentials-of-pediatrics.pdf
- Create embeddings
- Store in PostgreSQL (pgvector)
- Build knowledge graph in Neo4j

---

## 🔐 Security & Access

### Demo Credentials

After deployment, share these with your CEO and partners:

```
URL: https://your-app.vercel.app
Username: demo
Password: YourSecurePassword2025!
```

### Changing Credentials

To change the demo password:

1. Go to Render dashboard → Your web service
2. Environment tab
3. Update `DEMO_PASSWORD` value
4. Service will redeploy automatically

### Adding More Users (Future)

For production, consider upgrading to:
- JWT tokens
- User database
- OAuth 2.0
- Password hashing with bcrypt

---

## 📊 Monitoring & Maintenance

### Check Application Health

```bash
# Test backend health
curl https://doctorfollow-api.onrender.com/health

# Test authentication
curl -u demo:YourPassword https://doctorfollow-api.onrender.com/auth/login
```

### View Logs

**Backend Logs:**
1. Render dashboard → Your web service
2. "Logs" tab
3. Real-time logs and errors

**Frontend Logs:**
1. Vercel dashboard → Your project
2. "Deployments" → Latest deployment
3. "Build Logs" or "Runtime Logs"

### Database Access

**PostgreSQL:**
1. Render dashboard → Your database
2. "Shell" tab for SQL queries

**Neo4j:**
1. Neo4j Aura console
2. Click your instance → "Open with Neo4j Browser"

---

## 💰 Cost Management

### Current Free Tier Limits

| Service | Free Tier | Limits |
|---------|-----------|--------|
| Vercel | FREE forever | 100 GB bandwidth/month |
| Render Web | 750 hrs/month | Spins down after 15 min idle |
| Render PostgreSQL | 90 days FREE | 1 GB storage, then $7/month |
| Neo4j Aura | FREE forever | 200k nodes, 400k relationships |
| OpenAI API | Pay-per-use | ~$0.001 per 1K tokens |

### Expected Monthly Costs After Free Tier

- Vercel: **$0**
- Render Web: **$7/month** (if you want always-on)
- Render PostgreSQL: **$7/month**
- Neo4j: **$0**
- OpenAI: **~$5-10/month** (for demo usage)

**Total: ~$14-24/month** for production

### Staying on Free Tier Longer

- Keep using Render's free tier (handles sleep/wake)
- Migrate PostgreSQL to Supabase free tier after 90 days (500 MB free)
- Use free tier as long as possible for demo phase

---

## 🐛 Troubleshooting

### Issue: Frontend can't connect to backend

**Solution:**
1. Check CORS settings in Render
2. Ensure `ALLOWED_ORIGINS` includes your Vercel URL
3. Check browser console for CORS errors

### Issue: Authentication fails

**Solution:**
1. Check `DEMO_USERNAME` and `DEMO_PASSWORD` in Render environment
2. Clear browser cache
3. Check Render logs for authentication errors

### Issue: Backend spins down (takes time to load)

**Expected behavior on free tier**. Options:
1. Accept 30-second wake-up time
2. Upgrade to Render's $7/month plan for always-on
3. Use a ping service to keep it warm

### Issue: Database connection fails

**Solution:**
1. Check PostgreSQL credentials in Render environment
2. Ensure pgvector extension is installed
3. Check Render PostgreSQL logs

### Issue: Out of memory

**Solution:**
1. Render free tier has 512 MB RAM
2. Optimize your embedding model (use `e5-small` instead of `e5-large`)
3. Reduce batch sizes in ingestion scripts
4. Consider upgrading to Render's $7/month plan (512 MB → 1 GB)

---

## 📞 Getting Help

### Resources

- **Render Docs**: https://render.com/docs
- **Vercel Docs**: https://vercel.com/docs
- **Neo4j Aura Docs**: https://neo4j.com/docs/aura/
- **FastAPI Deployment**: https://fastapi.tiangolo.com/deployment/

### Community Support

- Render Discord: https://discord.gg/render
- Vercel Discord: https://discord.gg/vercel
- Neo4j Community: https://community.neo4j.com

---

## ✅ Post-Deployment Checklist

- [ ] Backend deployed to Render and responding
- [ ] Frontend deployed to Vercel and accessible
- [ ] PostgreSQL database created and pgvector enabled
- [ ] Neo4j knowledge graph created
- [ ] Medical documents ingested
- [ ] CORS configured correctly
- [ ] Authentication working (login page → chat)
- [ ] Test medical query returns results with sources
- [ ] Test casual query (no thinking section)
- [ ] Test Turkish query works
- [ ] Share demo credentials with CEO/partners
- [ ] Monitor usage and logs

---

## 🎉 Success!

Your DoctorFollow Medical AI Assistant is now live on the internet!

**Demo URL**: https://your-app.vercel.app
**API**: https://doctorfollow-api.onrender.com
**Username**: demo
**Password**: YourSecurePassword2025!

Share with your CEO and partners for testing. Good luck with your demo! 🚀

---

## 📈 Next Steps (After CEO Approval)

1. **Add more users**: Implement user database and registration
2. **Analytics**: Track usage, popular queries, response times
3. **Monitoring**: Set up Sentry or LogRocket for error tracking
4. **Caching**: Add Redis for faster responses
5. **Rate limiting**: Prevent API abuse
6. **Custom domain**: Get a professional domain name
7. **SSL certificate**: Vercel provides this automatically
8. **Backup strategy**: Regular database backups
9. **CI/CD pipeline**: Automated testing and deployment
10. **Production LLM**: Consider switching to AWS Bedrock for cost savings

---

**Generated**: 2025-10-21
**Version**: 1.0
**Author**: DoctorFollow Team
