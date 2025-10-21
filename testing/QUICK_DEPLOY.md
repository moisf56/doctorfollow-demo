# Quick Deployment Steps - DoctorFollow

## 🚀 Deploy in 15 Minutes

---

## Step 1: Push ONLY Testing Folder to GitHub (5 min)

```bash
# Navigate to testing folder
cd d:\DoctorFollow\DoctorFollow-Minimal-Demo\testing

# Initialize NEW git repo (only for testing folder)
git init
git add .
git commit -m "Production-ready with authentication"

# Create NEW repository on GitHub:
# 1. Go to github.com/new
# 2. Name: doctorfollow-demo
# 3. Click "Create repository"

# Then push (replace YOUR_USERNAME):
git remote add origin https://github.com/YOUR_USERNAME/doctorfollow-demo.git
git branch -M main
git push -u origin main
```

**Why?** This pushes ONLY the working `testing` folder, avoiding old/outdated files.

---

## Step 2: Deploy Backend to Render (5 min)

### 2.1 Create PostgreSQL Database

1. **Render Dashboard**: https://render.com/dashboard
2. Click "New +" → **PostgreSQL**
3. Settings:
   ```
   Name: doctorfollow-db
   Database: doctorfollow
   User: doctorfollow
   Region: Oregon (US West)
   Plan: Free
   ```
4. Click "Create Database"
5. **Wait 2 minutes**
6. Click "Info" → Copy **Internal Database URL** (save it)

### 2.2 Enable pgvector

1. Database page → **"Shell"** tab (at top)
2. Type:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
3. Press Enter → Should see `CREATE EXTENSION`

### 2.3 Deploy Backend

1. Click "New +" → **Web Service**
2. Select "Build and deploy from Git repository"
3. Connect GitHub → Select `doctorfollow-demo` repo
4. **Configure:**

   ```
   Name: doctorfollow-api
   Region: Oregon (US West)
   Branch: main
   Root Directory: (leave blank - we already pushed just testing folder)
   Runtime: Python 3
   ```

   **Build Command:**
   ```bash
   cd iteration_3 && pip install -r ../requirements.txt && python -m spacy download en_core_web_sm
   ```

   **Start Command:**
   ```bash
   cd iteration_3 && python api_server.py
   ```

   **Plan:** Free

5. **Click "Advanced" → Add Environment Variables:**

   **One by one, add these:**

   | Key | Value |
   |-----|-------|
   | `DEMO_USERNAME` | `demo` |
   | `DEMO_PASSWORD` | `DoctorFollow2025!` |
   | `ALLOWED_ORIGINS` | `http://localhost:3000` |
   | `LLM_PROVIDER` | `openai` |
   | `OPENAI_API_KEY` | `sk-your-real-key` |
   | `OPENAI_MODEL` | `gpt-4o-mini` |

   **Database (get from your Render PostgreSQL page):**

   | Key | Value (from your DB) |
   |-----|-------|
   | `POSTGRES_HOST` | `dpg-xxxxx.oregon-postgres.render.com` |
   | `POSTGRES_PORT` | `5432` |
   | `POSTGRES_DB` | `doctorfollow` |
   | `POSTGRES_USER` | `doctorfollow` |
   | `POSTGRES_PASSWORD` | `your-generated-password` |

   **Neo4j (optional - use dummy values for now):**

   | Key | Value |
   |-----|-------|
   | `NEO4J_URI` | `bolt://localhost:7687` |
   | `NEO4J_USER` | `neo4j` |
   | `NEO4J_PASSWORD` | `password` |

   **Embedding:**

   | Key | Value |
   |-----|-------|
   | `EMBEDDING_MODEL` | `intfloat/multilingual-e5-base` |
   | `EMBEDDING_DIMENSION` | `768` |

6. Click **"Create Web Service"**
7. **Wait 5-10 minutes** (watch logs - builds Python env, downloads spaCy model)
8. ✅ Your API URL: `https://doctorfollow-api.onrender.com`

**Test it:** Visit `https://doctorfollow-api.onrender.com/health` - should see `{"status":"healthy"}`

---

## Step 3: Deploy Frontend to Vercel (3 min)

### 3.1 Prepare Frontend

First, update API URL in code (if not already done):

Check `frontend/doctor-follow-app/src/App.js` line 5:
```javascript
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
```

✅ Already done if you're using the auth version.

### 3.2 Deploy

1. **Vercel Dashboard**: https://vercel.com/dashboard
2. Click "Add New..." → **Project**
3. Click "Import Git Repository"
4. Select `doctorfollow-demo`
5. **Configure:**

   ```
   Framework Preset: Create React App
   Root Directory: Click "Edit" → Type: frontend/doctor-follow-app
   Build Command: npm run build (auto-detected)
   Output Directory: build (auto-detected)
   ```

6. **Environment Variables:**

   Click "Add" under Environment Variables:

   | Key | Value |
   |-----|-------|
   | `REACT_APP_API_URL` | `https://doctorfollow-api.onrender.com` |

7. Click **"Deploy"**
8. **Wait 2-3 minutes**
9. ✅ Your app URL: `https://doctorfollow-demo-xxxxx.vercel.app`

---

## Step 4: Update CORS (1 min)

Backend needs to allow your frontend URL:

1. **Render** → `doctorfollow-api` service
2. **Environment** tab
3. Find `ALLOWED_ORIGINS`
4. Edit to (replace with your actual Vercel URL):
   ```
   https://doctorfollow-demo-xxxxx.vercel.app,http://localhost:3000
   ```
5. **Save** → Auto-redeploys in 2 min

---

## Step 5: Test It! (1 min)

1. Open your Vercel URL: `https://doctorfollow-demo-xxxxx.vercel.app`
2. **Login page** should appear
3. Enter:
   ```
   Username: demo
   Password: DoctorFollow2025!
   ```
4. Click "Sign In"
5. **Chat page** appears
6. Try: "Hello" → Should get friendly response

---

## ✅ SUCCESS!

**Share with CEO/Partners:**

```
URL: https://doctorfollow-demo-xxxxx.vercel.app
Username: demo
Password: DoctorFollow2025!
```

---

## 🐛 Quick Troubleshooting

### "Can't connect to server"
- Check Render backend is online (green status)
- Check CORS includes your Vercel URL
- Check browser console (F12) for errors

### "Authentication failed"
- Check `DEMO_USERNAME` and `DEMO_PASSWORD` in Render environment
- Try clearing browser cache

### "Backend takes 30 seconds first time"
- **Normal!** Free tier sleeps after 15 min idle
- Wakes up on first request

### "No medical answers"
- This is expected - you haven't loaded the PDF data yet
- Casual queries ("hello") will work
- Medical queries need data ingestion (see below)

---

## 📚 Load Medical Data (Optional - For Medical Queries)

Currently, only casual conversation works. To enable medical queries:

**Option 1: Quick Test (Skip for Demo)**
- Just demo casual conversations for CEO
- Medical data loading takes time

**Option 2: Load Data (Later)**
- Need to run ingestion script from local machine
- Requires Python environment setup
- Takes ~30 minutes to process PDF
- See DEPLOYMENT_GUIDE.md for full instructions

**For CEO demo, casual chat is enough to show the app works!**

---

## 💰 Cost

**First 90 days:** ~$0-5/month (OpenAI usage only)

**After:** ~$12-20/month

---

## 🎉 You're Live!

Your app is deployed and secured with login!

**Questions?** Check full [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)
