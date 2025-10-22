# DoctorFollow Backend Deployment Guide for Render.com

This guide will help you deploy the DoctorFollow Medical RAG backend API to Render.com.

## Prerequisites

Before deploying, ensure you have:

1. **Render.com Account** - Sign up at [render.com](https://render.com)
2. **GitHub Repository** - Your code should be in a Git repository
3. **External Services** (you'll need to set these up):
   - PostgreSQL database (can use Render's managed PostgreSQL)
   - Neo4j Aura instance (free tier available at [neo4j.com/cloud/aura](https://neo4j.com/cloud/aura))
   - Elasticsearch Cloud instance (Elastic Cloud Serverless at [cloud.elastic.co](https://cloud.elastic.co))
   - OpenAI API key (from [platform.openai.com](https://platform.openai.com))

## Files Ready for Deployment

Your deployment configuration is ready with these files:

- **[requirements.txt](requirements.txt)** - All Python dependencies
- **[runtime.txt](runtime.txt)** - Python version specification (3.11.9)
- **[Procfile](Procfile)** - Process command for Render
- **[render.yaml](render.yaml)** - Complete Render configuration (Infrastructure as Code)

## Deployment Methods

### Method 1: Automatic Deployment with render.yaml (Recommended)

This method uses the included `render.yaml` file for Infrastructure as Code deployment.

1. **Push your code to GitHub**
   ```bash
   git add .
   git commit -m "Ready for Render deployment"
   git push origin main
   ```

2. **Create New Blueprint Instance in Render**
   - Go to your Render Dashboard
   - Click "New" → "Blueprint"
   - Connect your GitHub repository
   - Select the repository containing your code
   - Render will automatically detect the `render.yaml` file
   - Click "Apply" to create all services

3. **Set Secret Environment Variables**

   After deployment, you need to set these secret values in the Render Dashboard:

   **Required Secrets:**
   ```
   OPENAI_API_KEY=sk-...
   NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
   NEO4J_PASSWORD=your-neo4j-password
   ES_URL=https://your-elastic-instance.es.region.cloud.es.io
   ES_API_KEY=your-elastic-api-key
   DEMO_PASSWORD=your-secure-password
   ```

   **Optional (if not using managed Postgres from Render):**
   ```
   POSTGRES_URL=postgresql://user:pass@host:port/database
   ```

4. **Update ALLOWED_ORIGINS** after deploying frontend
   - Once your frontend is deployed, update the `ALLOWED_ORIGINS` env var
   - Example: `https://your-frontend.vercel.app,http://localhost:3000`

### Method 2: Manual Web Service Creation

If you prefer manual setup:

1. **Create PostgreSQL Database** (if not already done)
   - In Render Dashboard, click "New" → "PostgreSQL"
   - Name: `doctorfollow-db`
   - Plan: Free (or Starter for production)
   - Region: Oregon (or your preferred region)
   - Click "Create Database"
   - Save the Internal Connection String

2. **Create Web Service**
   - Click "New" → "Web Service"
   - Connect your GitHub repository
   - Configure:
     - **Name**: `doctorfollow-api`
     - **Region**: Oregon (same as database)
     - **Branch**: main
     - **Root Directory**: `testing`
     - **Runtime**: Python 3
     - **Build Command**:
       ```
       cd iteration_3 && pip install --upgrade pip && pip install -r ../requirements.txt
       ```
     - **Start Command**:
       ```
       cd iteration_3 && python api_server.py
       ```

3. **Set Environment Variables** (see list above in Method 1)

4. **Deploy**
   - Click "Create Web Service"
   - Render will build and deploy your application

## Environment Variables Reference

### Authentication
- `DEMO_USERNAME` - Demo login username (default: "demo")
- `DEMO_PASSWORD` - Demo login password (set securely)

### CORS
- `ALLOWED_ORIGINS` - Comma-separated list of allowed frontend URLs

### LLM Provider
- `LLM_PROVIDER` - "openai" or "bedrock" (default: "openai")
- `OPENAI_API_KEY` - Your OpenAI API key
- `OPENAI_MODEL` - Model to use (default: "gpt-4o-mini")

### Database - PostgreSQL + pgvector
- `POSTGRES_URL` - Full connection string (auto-set if using Render's managed DB)
- Or individual components:
  - `POSTGRES_HOST`
  - `POSTGRES_PORT`
  - `POSTGRES_DB`
  - `POSTGRES_USER`
  - `POSTGRES_PASSWORD`

### Database - Neo4j (Knowledge Graph)
- `NEO4J_URI` - Neo4j Aura connection URI (neo4j+s://...)
- `NEO4J_USER` - Username (default: "neo4j")
- `NEO4J_PASSWORD` - Database password

### Database - Elasticsearch (BM25 Search)
- `ES_URL` - Elastic Cloud endpoint URL
- `ES_API_KEY` - API key for authentication
- `ES_INDEX_NAME` - Index name (default: "medical_chunks")

### Model Configuration
- `EMBEDDING_MODEL` - Sentence transformer model (default: "intfloat/multilingual-e5-large")
- `EMBEDDING_DIMENSION` - Embedding dimension (default: 1024)

### RAG Parameters (Optional)
- `CHUNK_SIZE` - Text chunk size (default: 400)
- `CHUNK_OVERLAP` - Chunk overlap (default: 100)
- `TOP_K_OPENSEARCH` - BM25 results to retrieve (default: 10)
- `TOP_K_PGVECTOR` - Semantic results to retrieve (default: 10)
- `TOP_K_FINAL` - Final fused results (default: 5)
- `RRF_K` - RRF fusion constant (default: 60)

## Setting Up External Services

### 1. Neo4j Aura (Knowledge Graph)

1. Go to [neo4j.com/cloud/aura](https://neo4j.com/cloud/aura)
2. Create a free AuraDB instance
3. Save the connection URI and password
4. Set in Render:
   - `NEO4J_URI`: The connection string (neo4j+s://...)
   - `NEO4J_PASSWORD`: The generated password

### 2. Elastic Cloud (BM25 Search)

1. Go to [cloud.elastic.co](https://cloud.elastic.co)
2. Create a free Elasticsearch Serverless instance
3. Create an API key for authentication
4. Set in Render:
   - `ES_URL`: Your Elasticsearch endpoint
   - `ES_API_KEY`: Your API key

### 3. OpenAI API

1. Go to [platform.openai.com](https://platform.openai.com)
2. Create an API key
3. Set in Render:
   - `OPENAI_API_KEY`: Your API key

## Post-Deployment Steps

1. **Verify Health Check**
   - Visit `https://your-app.onrender.com/health`
   - Should return `{"status": "healthy", ...}`

2. **Test API Documentation**
   - Visit `https://your-app.onrender.com/docs`
   - Interactive API documentation (Swagger UI)

3. **Test Authentication**
   - Use the `/auth/login` endpoint with your credentials
   - Or test directly in Swagger UI

4. **Initialize Databases**
   - You'll need to populate your databases with medical documents
   - Run your ingestion scripts (iteration_1, iteration_2, iteration_3 builders)

5. **Update Frontend**
   - Update your frontend's API endpoint to your Render URL
   - Add the frontend URL to `ALLOWED_ORIGINS`

## Troubleshooting

### Build Fails - PyTorch Installation

If PyTorch installation fails due to size:
- Use the free tier for testing, or upgrade to Starter plan
- PyTorch is required for sentence-transformers embeddings
- Consider using a smaller embedding model if needed

### Database Connection Errors

- Verify PostgreSQL URL is correct
- Ensure pgvector extension is enabled
- Check Neo4j credentials and URI format
- Verify Elasticsearch URL and API key

### Out of Memory Errors

- Upgrade to Starter plan (512MB RAM minimum recommended)
- Consider reducing `TOP_K_*` values to retrieve fewer results
- Use smaller embedding models if possible

### CORS Errors from Frontend

- Add your frontend URL to `ALLOWED_ORIGINS`
- Format: `https://yourapp.vercel.app,https://yourapp.netlify.app`
- Separate multiple URLs with commas (no spaces)

## Monitoring

- **Logs**: Available in Render Dashboard under your service
- **Metrics**: CPU, Memory, Request counts available in Dashboard
- **Health Check**: Automatic health checks on `/health` endpoint

## Scaling

For production use:
- Upgrade to **Starter Plan** ($7/month) for 512MB RAM
- Enable **Auto-Deploy** for continuous deployment
- Set up **Disk Storage** if caching embeddings locally
- Consider **Regional Deployment** closer to your users

## Security Best Practices

1. **Never commit secrets** - Use environment variables
2. **Use strong passwords** - For `DEMO_PASSWORD`
3. **Rotate API keys** - Regularly update OpenAI, Elastic, Neo4j keys
4. **Update ALLOWED_ORIGINS** - Only allow your actual frontend domains
5. **Use HTTPS** - Render provides free SSL certificates

## Cost Estimation

### Free Tier (for testing)
- Render Web Service: Free (with limitations)
- Render PostgreSQL: Free (1GB storage)
- Neo4j Aura: Free tier available
- Elastic Cloud: Free tier available
- **Total**: $0/month (with usage limits)

### Production Tier (recommended)
- Render Web Service: $7/month (Starter)
- Render PostgreSQL: $7/month (Starter)
- Neo4j Aura: Free or $65/month (Professional)
- Elastic Cloud: Free or $95/month (Standard)
- OpenAI API: Pay-as-you-go (~$0.15 per 1K tokens for gpt-4o-mini)
- **Total**: ~$14-200/month depending on database choices

## Support

- Render Documentation: [render.com/docs](https://render.com/docs)
- DoctorFollow Issues: [GitHub Issues](https://github.com/your-repo/issues)

## Next Steps

After successful deployment:
1. Test all API endpoints in Swagger UI
2. Deploy frontend to Vercel/Netlify
3. Update CORS settings with frontend URL
4. Ingest your medical documents
5. Monitor logs and performance
6. Set up alerting for downtime

---

**Deployment Checklist:**
- [ ] Code pushed to GitHub
- [ ] Render service created
- [ ] Environment variables set
- [ ] Neo4j Aura instance created
- [ ] Elastic Cloud instance created
- [ ] OpenAI API key obtained
- [ ] Health check passing
- [ ] API documentation accessible
- [ ] Frontend connected
- [ ] CORS configured
- [ ] Databases populated
- [ ] Production testing complete

Good luck with your deployment! 🚀
