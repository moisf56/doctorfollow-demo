"""
FastAPI Server for Medical RAG v3
Provides REST API endpoints for the frontend to interact with RAG system
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
import uvicorn
from pathlib import Path
import sys
import re
import json
import asyncio

# Add parent directories for imports
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "iteration_1"))
sys.path.append(str(Path(__file__).parent.parent / "iteration_2"))

from rag_v3 import MedicalRAGv3

# Initialize FastAPI app
app = FastAPI(
    title="Doctor Follow API",
    description="Medical RAG v3 API for cross-lingual medical question answering",
    version="3.0.0"
)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize RAG system (singleton)
rag_system: Optional[MedicalRAGv3] = None


@app.on_event("startup")
async def startup_event():
    """Initialize RAG system on startup"""
    global rag_system
    print("\n" + "="*80)
    print("INITIALIZING DOCTOR FOLLOW API SERVER")
    print("="*80)
    try:
        rag_system = MedicalRAGv3()
        print("\n[OK] RAG v3 system initialized successfully")
    except Exception as e:
        print(f"\n[ERROR] Failed to initialize RAG system: {e}")
        import traceback
        traceback.print_exc()
        raise


# Request/Response models
class Message(BaseModel):
    """Single message in conversation history"""
    role: str  # 'user' or 'assistant'
    content: str


class ChatRequest(BaseModel):
    """Chat request model with conversation history"""
    query: str
    conversation_history: Optional[List[Message]] = []

    class Config:
        schema_extra = {
            "example": {
                "query": "What is the treatment for PPHN in newborns?",
                "conversation_history": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hello Doctor! How can I help you today?"}
                ]
            }
        }


class Source(BaseModel):
    """Source document model"""
    chunk_id: str
    text: str
    page_number: int
    rrf_score: Optional[float] = None
    bm25_score: Optional[float] = None
    semantic_score: Optional[float] = None


class ChatResponse(BaseModel):
    """Chat response model"""
    query: str
    answer: str
    sources: List[Source]
    kg_context: Optional[str] = None
    num_sources: int
    detected_language: Optional[str] = None
    query_type: Optional[str] = None  # 'conversational' or 'medical'


# Helper functions for conversational AI
def classify_query_unified(query: str, conversation_history: List[Message]) -> tuple:
    """
    Single LLM call to detect language, classify type, and determine complexity

    Returns:
        tuple: (language, query_type, complexity) where:
        - language: 'en' or 'tr'
        - query_type: 'casual' or 'medical'
        - complexity: 'simple' or 'complex' (only for medical queries)
    """
    if rag_system is None or rag_system.llm is None:
        return ('en', 'medical', 'simple')

    # Build conversation context
    history_context = ""
    if conversation_history:
        recent_history = conversation_history[-4:]  # Last 2 exchanges
        for msg in recent_history:
            role = "Doctor" if msg.role == "user" else "Assistant"
            history_context += f"{role}: {msg.content}\n"

    classification_prompt = f"""You are a query classifier for a medical AI assistant.

Your task: Analyze the query and provide THREE pieces of information in ONE response:

1. Language: EN or TR
   - EN: English
   - TR: Turkish (contains Turkish characters like ğ, ü, ş, ı, ö, ç or Turkish words)

2. Type: CASUAL or MEDICAL
   - CASUAL: Greetings, small talk, thank you, how are you, casual conversation, daily tasks help
   - MEDICAL: Any question requiring medical knowledge, diagnosis, treatment, symptoms, medications

3. Complexity (ONLY if MEDICAL):
   - SIMPLE: Direct factual questions ("What is the dose of X?", "What causes Y?")
   - COMPLEX: Requires reasoning ("Differential diagnosis for...", "Treatment plan for...", "How do I manage...")

Recent conversation:
{history_context if history_context else "[No prior conversation]"}

Current query: {query}

Respond in this EXACT format (one line only):
[LANGUAGE], [TYPE]: [COMPLEXITY]

Examples:
- "en, casual: none" (English greeting)
- "tr, casual: none" (Turkish greeting like "merhaba")
- "en, medical: simple" (English factual question)
- "tr, medical: complex" (Turkish diagnostic question)

Classification:"""

    try:
        response = rag_system.llm.invoke(classification_prompt)
        result = response.content.strip().lower()

        # Parse response: "en, casual: none" or "tr, medical: complex"
        language = 'en'  # default
        query_type = 'medical'  # default
        complexity = 'simple'  # default

        # Extract language
        if result.startswith('tr'):
            language = 'tr'
        elif result.startswith('en'):
            language = 'en'

        # Extract type and complexity
        if ':' in result:
            # Split by comma first to separate language from type
            if ',' in result:
                parts = result.split(',', 1)
                type_complexity = parts[1].strip()
            else:
                type_complexity = result

            # Now split by colon
            if ':' in type_complexity:
                type_part, complexity_part = type_complexity.split(':', 1)

                # Parse type
                if 'casual' in type_part or 'conversational' in type_part:
                    query_type = 'casual'
                    complexity = 'none'
                else:
                    query_type = 'medical'
                    # Parse complexity
                    if 'complex' in complexity_part:
                        complexity = 'complex'
                    else:
                        complexity = 'simple'

        return (language, query_type, complexity)

    except Exception as e:
        print(f"[CLASSIFY ERROR] {e}")
        return ('en', 'medical', 'simple')  # Default on error


def generate_conversational_response_with_llm(query: str, conversation_history: List[Message], language: str = 'en') -> str:
    """
    Use LLM to generate a friendly conversational response without RAG

    Args:
        query: User's conversational query
        conversation_history: Previous conversation messages
        language: 'en' or 'tr'

    Returns:
        Conversational response
    """
    if rag_system is None or rag_system.llm is None:
        return "Hello! I'm your medical AI assistant. How can I help you today?"

    # Build conversation context
    history_context = ""
    if conversation_history:
        recent_history = conversation_history[-6:]  # Last 3 exchanges
        for msg in recent_history:
            role = "Doctor" if msg.role == "user" else "You"
            history_context += f"{role}: {msg.content}\n"

    # Language-specific instructions
    language_instruction = ""
    if language == 'tr':
        language_instruction = """CRITICAL: Respond in TURKISH (Türkçe). The doctor is speaking Turkish.
- Provide your ENTIRE response in Turkish
- Use natural, conversational Turkish
- Be warm and professional in Turkish"""
    else:
        language_instruction = """CRITICAL: Respond in ENGLISH.
- Provide your entire response in English
- Use natural, conversational English"""

    conversational_prompt = f"""You are a friendly medical AI assistant having a casual conversation with a doctor.

{language_instruction}

Your personality:
- Warm and professional
- Brief and natural (1-2 sentences)
- Ready to help with medical questions
- Don't provide medical information unless asked
- Respond naturally to greetings, thank yous, and small talk

Recent conversation:
{history_context if history_context else "[Start of conversation]"}

Doctor: {query}

Respond naturally and conversationally:"""

    try:
        response = rag_system.llm.invoke(conversational_prompt)
        return response.content.strip()
    except Exception as e:
        print(f"[CONVERSATIONAL ERROR] {e}")
        if language == 'tr':
            return "Merhaba! Size nasıl yardımcı olabilirim?"
        return "I'm here to help! Do you have any medical questions?"


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "Doctor Follow API",
        "version": "3.0.0",
        "rag_version": "v3",
        "features": [
            "Cross-lingual support (Turkish/English)",
            "Knowledge graph enrichment",
            "Hybrid retrieval (BM25 + Semantic)",
            "LangGraph workflow",
            "Conversational AI with LLM classification"
        ]
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    if rag_system is None:
        raise HTTPException(status_code=503, detail="RAG system not initialized")

    return {
        "status": "healthy",
        "rag_initialized": True,
        "components": {
            "opensearch": True,
            "pgvector": True,
            "neo4j": True,
            "llm": rag_system.llm is not None
        }
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint with conversational AI

    Flow:
    1. Classify query (conversational vs medical)
    2. If conversational: Generate friendly response without RAG
    3. If medical: Full RAG pipeline (retrieval + KG + LLM)
    """
    if rag_system is None:
        raise HTTPException(
            status_code=503,
            detail="RAG system not initialized. Please try again later."
        )

    if not request.query or not request.query.strip():
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty"
        )

    try:
        # Safe print for Unicode
        try:
            print(f"\n[API] Received query: {request.query}")
        except UnicodeEncodeError:
            print("\n[API] Received query: [Unicode text]")

        # Step 1: Unified classification (1 LLM call for language + type + complexity)
        language, query_type, complexity = classify_query_unified(request.query, request.conversation_history or [])

        try:
            print(f"[API] Query classified as: language={language}, type={query_type}, complexity={complexity}")
        except UnicodeEncodeError:
            print(f"[API] Query classified")

        # Step 2: Handle based on query type
        if query_type == 'casual':
            # Generate conversational response without RAG
            answer = generate_conversational_response_with_llm(
                request.query,
                request.conversation_history or [],
                language
            )

            response = ChatResponse(
                query=request.query,
                answer=answer,
                sources=[],  # No sources for conversational responses
                kg_context=None,
                num_sources=0,
                detected_language=None,
                query_type='casual'
            )

            try:
                print(f"[API] Casual response generated")
            except UnicodeEncodeError:
                print(f"[API] Response generated")

        else:
            # Medical query - use RAG pipeline with language and complexity
            result = rag_system.ask(request.query, language=language, complexity=complexity)

            # Convert sources to response model
            sources = [
                Source(
                    chunk_id=src["chunk_id"],
                    text=src["text"],
                    page_number=src["page_number"],
                    rrf_score=src.get("rrf_score"),
                    bm25_score=src.get("bm25_score"),
                    semantic_score=src.get("semantic_score")
                )
                for src in result["sources"]
            ]

            response = ChatResponse(
                query=result["query"],
                answer=result["answer"],
                sources=sources,
                kg_context=result.get("kg_context"),
                num_sources=result["num_sources"],
                detected_language=None,
                query_type='medical'
            )

            try:
                print(f"[API] Medical response generated ({len(result['answer'])} chars)")
            except UnicodeEncodeError:
                print(f"[API] Medical response generated")

        return response

    except Exception as e:
        try:
            print(f"[API ERROR] {str(e)}")
        except UnicodeEncodeError:
            print("[API ERROR] Unicode error")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Streaming chat endpoint with real-time thinking steps

    Streams JSON events:
    - {type: "thinking_start"}
    - {type: "thinking", content: "..."}
    - {type: "thinking_end"}
    - {type: "answer_start"}
    - {type: "answer", content: "..."}
    - {type: "answer_end"}
    - {type: "references", content: "..."}
    - {type: "done"}
    """
    if rag_system is None:
        raise HTTPException(status_code=503, detail="RAG system not initialized")

    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    async def generate():
        try:
            # Step 1: Unified classification (1 LLM call for language + type + complexity)
            language, query_type, complexity = classify_query_unified(request.query, request.conversation_history or [])

            # Handle casual queries (no RAG, no thinking section)
            if query_type == 'casual':
                answer = generate_conversational_response_with_llm(
                    request.query,
                    request.conversation_history or [],
                    language
                )
                yield f"data: {json.dumps({'type': 'answer', 'content': answer})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return

            # Medical query - show thinking section
            yield f"data: {json.dumps({'type': 'thinking_start'})}\n\n"

            yield f"data: {json.dumps({'type': 'thinking', 'content': '• Analyzing query...\n'})}\n\n"
            await asyncio.sleep(0.15)

            # Send classification results as thinking steps
            lang_display = "Turkish" if language == "tr" else "English"
            yield f"data: {json.dumps({'type': 'thinking', 'content': f'• Language detected: {lang_display}\n'})}\n\n"
            await asyncio.sleep(0.15)

            yield f"data: {json.dumps({'type': 'thinking', 'content': f'• Complexity level: {complexity.upper()}\n'})}\n\n"
            await asyncio.sleep(0.15)

            # Medical query - show retrieval steps
            yield f"data: {json.dumps({'type': 'thinking', 'content': '• Retrieving relevant medical information...\n'})}\n\n"
            await asyncio.sleep(0.2)

            if complexity == 'complex':
                yield f"data: {json.dumps({'type': 'thinking', 'content': '• Enriching with knowledge graph...\n'})}\n\n"
                await asyncio.sleep(0.2)

            yield f"data: {json.dumps({'type': 'thinking', 'content': '• Analyzing medical context...\n'})}\n\n"
            await asyncio.sleep(0.2)

            yield f"data: {json.dumps({'type': 'thinking', 'content': '• Formulating evidence-based response...\n'})}\n\n"
            await asyncio.sleep(0.2)

            # Medical query - RAG with language and conditional KG based on complexity
            result = rag_system.ask(request.query, language=language, complexity=complexity)
            full_answer = result["answer"]

            # Parse the answer for reasoning, answer, and references
            reasoning = ''
            answer = ''
            references = ''

            # Extract reasoning
            reasoning_match = re.search(r'<reasoning>([\s\S]*?)</reasoning>', full_answer)
            if reasoning_match:
                reasoning = reasoning_match.group(1).strip()
                full_answer = full_answer.replace(reasoning_match.group(0), '').strip()

            # Extract answer
            answer_match = re.search(r'<answer>([\s\S]*?)</answer>', full_answer)
            if answer_match:
                answer = answer_match.group(1).strip()
                full_answer = full_answer.replace(answer_match.group(0), '').strip()
            else:
                # No <answer> tags, use split logic
                if '---' in full_answer:
                    parts = full_answer.split('---')
                    answer = parts[0].strip()
                    references = parts[1].strip() if len(parts) > 1 else ''
                else:
                    answer = full_answer

            # Extract references if not already done
            if not references and '---' in full_answer:
                parts = full_answer.split('---')
                references = parts[1].strip() if len(parts) > 1 else ''

            # Stream reasoning (Chain-of-Thought thinking steps)
            if reasoning:
                # Split reasoning into steps and stream them
                steps = reasoning.split('\n')
                for step in steps:
                    if step.strip():
                        await asyncio.sleep(0.05)  # Small delay for visual effect
                        yield f"data: {json.dumps({'type': 'thinking', 'content': step + '\n'})}\n\n"

            # End thinking section
            yield f"data: {json.dumps({'type': 'thinking_end'})}\n\n"

            # Stream answer
            yield f"data: {json.dumps({'type': 'answer_start'})}\n\n"

            # Stream answer character by character for more real-time feel
            # This simulates token-level streaming
            for char in answer:
                await asyncio.sleep(0.01)  # Fast character streaming
                yield f"data: {json.dumps({'type': 'answer', 'content': char})}\n\n"

            yield f"data: {json.dumps({'type': 'answer_end'})}\n\n"

            # Send references
            if references:
                yield f"data: {json.dumps({'type': 'references', 'content': references})}\n\n"

            # Send sources
            sources_data = [
                {
                    'chunk_id': src['chunk_id'],
                    'text': src['text'],
                    'page_number': src['page_number']
                }
                for src in result['sources']
            ]
            yield f"data: {json.dumps({'type': 'sources', 'data': sources_data})}\n\n"

            # Done
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            yield f"data: {json.dumps({'type': 'error', 'content': error_msg})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("STARTING DOCTOR FOLLOW API SERVER")
    print("="*80)
    print("\nServer will be available at:")
    print("  - Local: http://localhost:8000")
    print("  - Docs:  http://localhost:8000/docs")
    print("\nPress Ctrl+C to stop the server")
    print("="*80 + "\n")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
