# Quick Deployment Steps

## ✅ What's Already Done

1. ✅ Backend deployed on Render: `https://doctorfollow-api-3voo.onrender.com`
2. ✅ Frontend CORS configured in `api_server.py`
3. ✅ `.env.production` created with Render URL
4. ✅ `vercel.json` created
5. ✅ `render.yaml` updated with Vercel URL

---

## 🚀 Next Steps

### Step 1: Update Render Environment Variable

**Important:** You need to add the ALLOWED_ORIGINS environment variable to Render dashboard.

1. Go to: https://dashboard.render.com/
2. Click on your service: `doctorfollow-api`
3. Go to **Environment** tab
4. Click **Add Environment Variable**
5. Add:
   ```
   Key: ALLOWED_ORIGINS
   Value: http://localhost:3000,http://localhost:3001,https://doctorfollow-demo.vercel.app
   ```
6. Click **Save Changes**
7. **Wait for automatic redeploy** (~2-3 minutes)

### Step 2: Deploy Frontend to Vercel

#### Option A: Using Vercel CLI (Recommended)

```bash
# 1. Navigate to frontend directory
cd testing/frontend/doctor-follow-app

# 2. Install Vercel CLI (if not installed)
npm install -g vercel

# 3. Login to Vercel
vercel login

# 4. Deploy to production
vercel --prod

# Follow the prompts:
# - Set up and deploy? Yes
# - Which scope? (your account)
# - Link to existing project? Yes (if you already created doctorfollow-demo project)
# - Or: Project name: doctorfollow-demo (if new)
```

#### Option B: Using Vercel Dashboard

1. **Make sure changes are committed:**
   ```bash
   cd testing/frontend/doctor-follow-app
   git add .
   git commit -m "Configure production API URL and CORS"
   git push
   ```

2. **Trigger Redeploy on Vercel:**
   - Go to: https://vercel.com/dashboard
   - Find your project: `doctorfollow-demo`
   - Click **Deployments** tab
   - Click **Redeploy** on latest deployment
   - Or: Make any change and push to trigger auto-deploy

3. **Verify Environment Variable:**
   - Go to: Settings → Environment Variables
   - Ensure `REACT_APP_API_URL` is set to: `https://doctorfollow-api-3voo.onrender.com`
   - If not, add it and redeploy

### Step 3: Test the Connection

#### A. Test Backend Health
```bash
curl https://doctorfollow-api-3voo.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2025-..."
}
```

#### B. Test Frontend
1. Open: https://doctorfollow-demo.vercel.app
2. You should see the login page
3. Open browser console (F12 → Console)
4. Check for any errors

#### C. Test Login
1. Enter credentials:
   - Username: `demo`
   - Password: Check Render dashboard → Environment → `DEMO_PASSWORD` value
2. Click **Sign In**
3. Should redirect to chat interface

#### D. Test Chat
1. Ask: "What is RDS treatment?"
2. Wait for response (first request may take 15-30 seconds if backend was idle)
3. Check that you get a streaming response with:
   - Clinical Reasoning (collapsible)
   - Answer
   - References (sources)

---

## 🔍 Troubleshooting

### Issue 1: CORS Error in Console

**Symptom:**
```
Access to fetch at 'https://doctorfollow-api-3voo.onrender.com/...'
has been blocked by CORS policy
```

**Fix:**
1. Verify `ALLOWED_ORIGINS` is set in Render dashboard
2. Make sure there are no spaces in the URL list
3. Restart Render service (Settings → Manual Deploy)
4. Clear browser cache (Ctrl+Shift+Delete → Cached images and files)

### Issue 2: 401 Unauthorized

**Symptom:**
Login fails with "Invalid username or password"

**Fix:**
1. Go to Render dashboard → Environment
2. Find `DEMO_PASSWORD` value (click "Reveal")
3. Use that exact password (it's auto-generated)
4. Or update it to a known value: `DoctorFollow2025!`

### Issue 3: Connection Timeout

**Symptom:**
```
Failed to fetch / Network error / Timeout
```

**Fix:**
1. Check if backend is running: https://doctorfollow-api-3voo.onrender.com/health
2. If it returns 503 or timeout:
   - Backend is "cold starting" (free tier spins down after 15 min idle)
   - Wait 30-60 seconds and try again
   - First request will wake it up

### Issue 4: Frontend Shows Wrong API URL

**Symptom:**
Console shows: `API URL: http://localhost:8000`

**Fix:**
1. Make sure `.env.production` exists in `doctor-follow-app/`
2. Verify it contains: `REACT_APP_API_URL=https://doctorfollow-api-3voo.onrender.com`
3. Rebuild and redeploy:
   ```bash
   npm run build
   vercel --prod
   ```

---

## 📊 Expected Behavior

### First Request (Cold Start)
- **Time**: 15-30 seconds
- **Reason**: Render free tier "wakes up" the backend
- **Solution**: This is normal, subsequent requests will be fast

### Normal Request
- **Login**: 1-2 seconds
- **Chat query**: 2-5 seconds (includes Jina AI API call)
- **Streaming**: Real-time token-by-token response

### Performance Tips
1. **Keep Backend Warm**: Ping `/health` every 14 minutes
2. **Upgrade to Render Starter**: $7/month, no cold starts
3. **Use Vercel Analytics**: Monitor frontend performance

---

## 🎯 Quick Test Commands

```bash
# Test backend health
curl https://doctorfollow-api-3voo.onrender.com/health

# Test backend auth (replace PASSWORD with actual password from Render)
curl -X POST https://doctorfollow-api-3voo.onrender.com/auth/login \
  -H "Content-Type: application/json" \
  -u demo:PASSWORD

# Check frontend build locally
cd testing/frontend/doctor-follow-app
npm run build
npm install -g serve
serve -s build -p 3000

# Then open: http://localhost:3000
```

---

## 🔐 Security Checklist

- [x] HTTPS enabled (automatic on Render + Vercel)
- [x] HTTP Basic Auth configured
- [x] CORS restricted to specific origins
- [x] Credentials stored in sessionStorage (not localStorage)
- [x] Environment variables used for secrets
- [ ] TODO: Rotate `DEMO_PASSWORD` after testing
- [ ] TODO: Set up custom domain (optional)
- [ ] TODO: Enable Vercel password protection (optional)

---

## 📞 Getting Your Demo Password

Your Render service auto-generated a secure password. To find it:

1. Go to: https://dashboard.render.com/
2. Click your service: `doctorfollow-api`
3. Go to **Environment** tab
4. Find `DEMO_PASSWORD`
5. Click **Reveal** to see the value
6. Use this password for login

Or update it to something easier to remember:
1. Click **Edit** on `DEMO_PASSWORD`
2. Change value to: `DoctorFollow2025!`
3. Click **Save Changes**
4. Wait for redeploy

---

## ✅ Final Checklist

Before going live:

- [ ] Backend `ALLOWED_ORIGINS` includes Vercel URL
- [ ] Frontend `.env.production` has correct Render URL
- [ ] Vercel environment variable `REACT_APP_API_URL` is set
- [ ] Backend health endpoint returns 200 OK
- [ ] Login works with correct credentials
- [ ] Chat query returns streaming response
- [ ] Sources/references display correctly
- [ ] No CORS errors in console
- [ ] No 401/403 errors

---

## 🎉 Your Live URLs

- **Frontend**: https://doctorfollow-demo.vercel.app
- **Backend**: https://doctorfollow-api-3voo.onrender.com
- **Backend Health**: https://doctorfollow-api-3voo.onrender.com/health
- **API Docs**: https://doctorfollow-api-3voo.onrender.com/docs

---

**Ready to go! 🚀**
