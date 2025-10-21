# Frontend-Backend Integration Guide

## Overview

This guide explains how to run the integrated Doctor Follow system with:
- **Backend**: FastAPI server (RAG v3) on port 8000
- **Frontend**: React app on port 3000

---

## Prerequisites

### Backend Requirements
1. Python virtual environment activated
2. All dependencies installed (see `requirements.txt`)
3. OpenSearch running (port 9200)
4. PostgreSQL with pgvector running (port 5432)
5. Neo4j running (port 7687)
6. AWS credentials configured for Bedrock
7. `.env` file configured in `testing/` directory

### Frontend Requirements
1. Node.js installed
2. npm dependencies installed (`npm install`)

---

## Quick Start

### Step 1: Start Backend Server

**Option A: Using the startup script (Windows)**
```bash
cd testing/iteration_3
start_server.bat
```

**Option B: Manual start**
```bash
cd testing/iteration_3
..\venvsdoctorfollow\Scripts\activate
python api_server.py
```

The backend will be available at:
- API: http://localhost:8000
- Interactive API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### Step 2: Start Frontend

```bash
cd testing/frontend/doctor-follow-app
npm start
```

The frontend will open automatically at http://localhost:3000

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   INTEGRATED SYSTEM                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Frontend (React)          Backend (FastAPI)                │
│  Port 3000                 Port 8000                        │
│                                                             │
│  ┌──────────────┐         ┌──────────────┐                 │
│  │   User UI    │         │  API Server  │                 │
│  │              │ POST    │              │                 │
│  │  - Chat UI   │────────>│  /chat       │                 │
│  │  - Voice     │ /chat   │              │                 │
│  │  - Loading   │<────────│  JSON        │                 │
│  └──────────────┘         └──────┬───────┘                 │
│                                  │                          │
│                                  ▼                          │
│                          ┌──────────────┐                   │
│                          │  RAG v3      │                   │
│                          │  LangGraph   │                   │
│                          └──────┬───────┘                   │
│                                 │                           │
│              ┌──────────────────┼──────────────────┐        │
│              │                  │                  │        │
│              ▼                  ▼                  ▼        │
│       ┌────────────┐    ┌────────────┐    ┌────────────┐   │
│       │ OpenSearch │    │ pgvector   │    │   Neo4j    │   │
│       │   (BM25)   │    │ (Semantic) │    │   (KG)     │   │
│       └────────────┘    └────────────┘    └────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## API Endpoints

### 1. Health Check
```bash
GET http://localhost:8000/health
```

**Response:**
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

### 2. Chat Query
```bash
POST http://localhost:8000/chat
Content-Type: application/json

{
  "query": "What is the treatment for PPHN in newborns?"
}
```

**Response:**
```json
{
  "query": "What is the treatment for PPHN in newborns?",
  "answer": "The treatment for PPHN (Persistent Pulmonary Hypertension...",
  "sources": [
    {
      "chunk_id": "chunk_123",
      "text": "PPHN treatment involves...",
      "page_number": 245,
      "rrf_score": 0.85
    }
  ],
  "kg_context": "Knowledge graph relationships: PPHN -> TREATS -> [oxygen, surfactant]...",
  "num_sources": 5,
  "detected_language": "en"
}
```

---

## Frontend Features

### 1. Real-time API Integration
- Automatic connection to backend at `http://localhost:8000`
- Loading states during API calls
- Error handling with user-friendly messages

### 2. UI Components
- **Chat interface**: Message history with user/AI distinction
- **Loading indicator**: Animated dots while processing
- **Voice input**: Speech-to-text (browser-based)
- **Send button**: Disabled during loading to prevent double submission

### 3. Color Scheme
- **User messages**: Orange/amber avatar + dark blue gradient bubble
- **AI messages**: Purple/blue avatar + dark gray bubble
- **Brand consistency**: Matches header gradient

---

## Testing the Integration

### Test 1: Simple English Query
```
User: "What is RDS in newborns?"
Expected: AI responds with information about Respiratory Distress Syndrome
```

### Test 2: Turkish Query
```
User: "PPHN tedavisi nedir?"
Expected: AI responds in Turkish with PPHN treatment information
```

### Test 3: Complex Clinical Query
```
User: "A term baby shows central cyanosis immediately after birth. What's the differential diagnosis?"
Expected: AI provides detailed differential diagnosis with citations
```

---

## Troubleshooting

### Backend Issues

**Error: "RAG system not initialized"**
- Check that OpenSearch, PostgreSQL, and Neo4j are running
- Verify `.env` file has correct database credentials
- Check AWS credentials for Bedrock access

**Error: "Connection refused" (port 8000)**
- Ensure backend server is running: `python api_server.py`
- Check for port conflicts

### Frontend Issues

**Error: "Failed to fetch"**
- Verify backend is running at http://localhost:8000
- Check browser console for CORS errors
- Ensure CORS middleware is configured in backend

**Error: "API error: 503"**
- Backend services not initialized
- Check backend logs for initialization errors

### CORS Issues
If you see CORS errors in browser console:
1. Verify CORS middleware in `api_server.py`
2. Check that React dev server is on port 3000
3. Try clearing browser cache

---

## File Structure

```
testing/
├── iteration_3/
│   ├── api_server.py           # FastAPI backend server
│   ├── rag_v3.py              # RAG v3 implementation
│   ├── requirements.txt       # Python dependencies
│   ├── start_server.bat       # Windows startup script
│   └── INTEGRATION_GUIDE.md   # This file
│
├── frontend/
│   └── doctor-follow-app/
│       ├── src/
│       │   └── App.js         # React app with API integration
│       ├── package.json       # Node dependencies
│       └── README.md          # Frontend README
│
└── .env                       # Environment variables
```

---

## Environment Variables

Ensure your `.env` file in `testing/` has:

```env
# OpenSearch
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200
OPENSEARCH_INDEX=medical_docs

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=medical_rag
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# AWS Bedrock
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0

# Embeddings
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
```

---

## Performance Notes

### Expected Latency
- **Language detection**: ~1-2s
- **Hybrid retrieval**: ~2-3s
- **KG enrichment**: ~1-2s
- **LLM generation**: ~3-5s
- **Total**: ~7-12 seconds per query

### Optimization Tips
1. **Caching**: Implement Redis for frequently asked questions
2. **Connection pooling**: Reuse database connections
3. **Batch processing**: Process multiple queries in parallel
4. **CDN**: Serve frontend assets via CDN

---

## Next Steps

### Production Deployment
1. **Containerization**: Create Docker containers for frontend and backend
2. **Load balancing**: Use nginx or AWS ALB
3. **Monitoring**: Add logging, metrics, and alerts
4. **Security**: Add authentication and rate limiting
5. **Scaling**: Deploy on Kubernetes or AWS ECS

### Feature Enhancements
1. **Chat history**: Persist conversations in database
2. **Source citations**: Show clickable references
3. **Feedback system**: Allow users to rate responses
4. **Export**: Download chat transcripts
5. **Multi-modal**: Support image uploads

---

## Support

For issues or questions:
1. Check backend logs: `api_server.py` console output
2. Check frontend console: Browser DevTools
3. Review API documentation: http://localhost:8000/docs
4. Check database connections: http://localhost:8000/health

---

**Built for**: Medical LLM Competition
**Version**: 3.0.0
**Last Updated**: 2025-01-19
