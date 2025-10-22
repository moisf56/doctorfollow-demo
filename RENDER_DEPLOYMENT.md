

# Demo Password (generate a strong one or use your own)
DEMO_PASSWORD=YourStrongPasswordHere123!
```

**To set these in Render:**
1. Go to your service in Render Dashboard
2. Click **"Environment"** tab
3. Click **"Add Environment Variable"**
4. Add each secret one by one
5. Click **"Save Changes"**

### Step 4: Verify Deployment

1. **Check Build Logs**
   - Watch the build process in Render Dashboard
   - Should see: Installing dependencies → Starting server
   - Build time: ~5-10 minutes (torch/transformers are large)

2. **Check Health Endpoint**
   - Once deployed, visit: `https://your-app.onrender.com/health`
   - Should return:
     ```json
     {
       "status": "healthy",
       "rag_initialized": true,
       "components": {
         "opensearch": true,
         "pgvector": true,
         "neo4j": true,
         "llm": true
       }
     }
     ```

3. **Test API Docs**
   - Visit: `https://your-app.onrender.com/docs`
   - Interactive Swagger UI should load
   - Test the `/auth/login` endpoint with credentials

4. **Test Chat Endpoint**
   - Use Swagger UI or curl:
     ```bash
     curl -X POST "https://your-app.onrender.com/chat" \
       -u "demo:YourPassword" \
       -H "Content-Type: application/json" \
       -d '{
         "query": "What is RDS treatment?",
         "conversation_history": []
       }'
     ```

---

## 🎯 Post-Deployment Steps

### 1. Update Frontend CORS

Once deployed, update the `ALLOWED_ORIGINS` environment variable:

```bash
# In Render Dashboard → Environment
ALLOWED_ORIGINS=https://your-frontend.vercel.app,http://localhost:3000
```

### 2. Get Your API URL

Your backend will be available at:
```
https://doctorfollow-api.onrender.com
```

Update your frontend to use this URL.

### 3. Test Knowledge Graph Enrichment

Send a **complex query** (Turkish or English):

```json
{
  "query": "Zamanında doğan bir bebek, doğumdan 6 saat sonra taşipne (60/dk), inleme ve interkostal çekilmeler gösteriyor. Akciğer grafisinde bilateral granüler patern ve hava bronkogramları görülüyor. En olası tanı nedir ve ilk basamak tedavi ne olmalıdır?",
  "conversation_history": []
}
```

**Expected logs:**
```
[HYBRID RETRIEVE] Query: ... (complexity: complex)
[KG ENRICH] Expanding with knowledge graph...
[OK] Added knowledge graph context (XXX chars)
[GENERATE] Creating answer...
```

✅ Knowledge Graph is working if you see `[OK] Added knowledge graph context`!

---

## ⚙️ Configuration Summary

### Environment Variables (render.yaml)

| Variable | Value | Notes |
|----------|-------|-------|
| `LLM_PROVIDER` | `openai` | Using OpenAI (can switch to bedrock) |
| `OPENAI_MODEL` | `gpt-4o-mini` | Cost-effective model |
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-small` | **Must match indexed embeddings!** |
| `EMBEDDING_DIMENSION` | `384` | **Must match model!** |
| `ES_INDEX_NAME` | `doctor_follow_medical_chunks` | Your Elasticsearch index |
| `NEO4J_URI` | `neo4j+ssc://...` | **Important: Use +ssc scheme!** |
| `TOP_K_FINAL` | `5` | Number of sources returned |

### Important Notes

⚠️ **Embedding Model**: `intfloat/multilingual-e5-small` with dimension `384`
- This **MUST** match what you used during indexing
- Changing this will break semantic search
- If you need to change it, you must re-index all documents

⚠️ **Neo4j URI Scheme**: Must use `neo4j+ssc://`
- `neo4j+s://` = Full certificate verification (will fail)
- `neo4j+ssc://` = Self-signed certificates accepted (works with Aura)

---

## 🐛 Troubleshooting

### Build Fails

**Issue:** PyTorch installation timeout
- **Solution:** Upgrade to Starter plan ($7/month) for more build time

**Issue:** Out of memory during build
- **Solution:** Upgrade to Starter plan for more RAM

### Neo4j Connection Fails

**Issue:** SSL certificate error
- **Solution:** Verify `NEO4J_URI` uses `neo4j+ssc://` scheme
- Check environment variable is set correctly

**Issue:** Authentication failed
- **Solution:** Verify `NEO4J_PASSWORD` matches Aura password

### Elasticsearch Connection Fails

**Issue:** Connection timeout
- **Solution:** Check `ES_URL` includes `https://` and port `:443`
- Verify `ES_API_KEY` is correct (no extra spaces)

### Knowledge Graph Not Enriching

**Issue:** Seeing `[INFO] No additional KG context found`
- **Cause:** Knowledge Graph is empty in Neo4j
- **Solution:** You need to **rebuild KG on Render** or **copy data from local**

**Option A: Rebuild on Render (Not Recommended - expensive)**
```bash
# SSH into Render shell (if available)
cd testing/iteration_3
python build_knowledge_graph.py
```

**Option B: Use Existing KG (Recommended)**
- Your local Neo4j already has the KG (402 nodes, 1,483 relationships)
- **Just use the same Neo4j Aura instance** - data is already there!
- ✅ No rebuild needed - you're using cloud Neo4j Aura

---

## 💰 Cost Estimate

### Render.com
- **Free Tier**: $0/month (sleeps after inactivity, slower)
- **Starter Tier**: $7/month (recommended for production)

### External Services
- **PostgreSQL**: Already have on Render
- **Neo4j Aura**: Free tier (already setup)
- **Elasticsearch Cloud**: Free tier (already setup)
- **OpenAI API**: ~$0.15 per 1K tokens (gpt-4o-mini)

**Total Monthly Cost**: $0-7 (Render) + OpenAI usage (~$5-20/month typical)

---

## 📊 Monitoring

### Logs
- **Real-time logs**: Render Dashboard → Logs tab
- **Filter by**: Error, Warning, Info

### Metrics
- **CPU/Memory**: Render Dashboard → Metrics
- **Request count**: Built-in analytics
- **Response time**: Health check monitoring

### Health Checks
Render automatically monitors `/health` endpoint:
- **Healthy**: Returns 200 OK
- **Unhealthy**: Automatically restarts service

---

## 🔒 Security Checklist

- [ ] Strong `DEMO_PASSWORD` set
- [ ] CORS configured with actual frontend URL (not wildcards)
- [ ] API keys stored as secret environment variables (not in code)
- [ ] GitHub repo is private (if needed)
- [ ] PostgreSQL has strong password
- [ ] Neo4j has strong password

---

## 🎉 You're Ready!

**Everything is prepared for deployment:**

✅ Code ready
✅ Dependencies verified
✅ Knowledge Graph built (402 nodes)
✅ All connections tested locally
✅ Configuration files updated
✅ Environment variables documented

**Next command:**
```bash
git add .
git commit -m "Ready for Render deployment"
git push origin main
```

Then deploy on Render Dashboard! 🚀

---

## 📞 Support

- **Render Docs**: https://render.com/docs
- **Neo4j Aura Support**: https://aura.support.neo4j.com
- **Elasticsearch Support**: https://cloud.elastic.co/support

Good luck with your deployment! 🎊
