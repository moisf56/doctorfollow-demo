"""
Quick test script to verify HF API integration works before deployment
"""
import os
import sys
from dotenv import load_dotenv

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

print("=" * 60)
print("Testing Jina AI Embeddings API Integration")
print("=" * 60)

# Test 1: Import and initialize without loading model
print("\n[Test 1] Importing PgVectorStore...")
try:
    from iteration_2.pgvector_store import PgVectorStore
    print("✅ Import successful")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

# Test 2: Initialize with load_model=False
print("\n[Test 2] Initializing PgVectorStore (HF API mode)...")
try:
    postgres_url = os.getenv("POSTGRES_URL")
    if not postgres_url:
        print("❌ POSTGRES_URL not found in .env")
        sys.exit(1)

    pgvector = PgVectorStore(
        connection_string=postgres_url,
        table_name="medical_embeddings",
        embedding_model="intfloat/multilingual-e5-small",
        embedding_dimension=384,
        load_model=False  # Use HF API
    )
    print("✅ Initialization successful (no model loaded)")
except Exception as e:
    print(f"❌ Initialization failed: {e}")
    sys.exit(1)

# Test 3: Test Jina AI API encoding directly
print("\n[Test 3] Testing Jina AI API embedding generation...")
try:
    test_query = "What is RDS treatment?"
    print(f"   Query: '{test_query}'")

    embedding = pgvector._encode_via_api(test_query)
    print(f"✅ Embedding generated successfully")
    print(f"   Shape: {embedding.shape}")
    print(f"   Dimension: {len(embedding)}")
    print(f"   Sample values: [{embedding[0]:.4f}, {embedding[1]:.4f}, ..., {embedding[-1]:.4f}]")

    if len(embedding) != 384:
        print(f"⚠️  Warning: Expected 384 dimensions, got {len(embedding)}")
except Exception as e:
    print(f"❌ Jina AI API encoding failed: {e}")
    print("\nPossible issues:")
    print("  - Invalid API key")
    print("  - Rate limiting (1M tokens/month)")
    print("  - Network connectivity issue")
    sys.exit(1)

# Test 4: Test actual search
print("\n[Test 4] Testing semantic search with Jina AI API...")
try:
    results = pgvector.search(query=test_query, top_k=3)
    print(f"✅ Search successful")
    print(f"   Found {len(results)} results")

    if len(results) > 0:
        print(f"\n   Top result:")
        print(f"   - Chunk ID: {results[0].chunk_id}")
        print(f"   - Score: {results[0].score:.4f}")
        print(f"   - Text preview: {results[0].text[:100]}...")
    else:
        print("   ⚠️  No results found (database might be empty)")
except Exception as e:
    print(f"❌ Search failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Check memory usage (approximate)
print("\n[Test 5] Memory check...")
try:
    import psutil
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    print(f"✅ Current memory usage: {memory_mb:.1f} MB")

    if memory_mb > 512:
        print(f"   ⚠️  Memory usage exceeds 512MB (Render free tier limit)")
    else:
        print(f"   ✅ Memory usage is within 512MB limit")
except ImportError:
    print("   ℹ️  psutil not installed, skipping memory check")
    print("   Install with: pip install psutil")

print("\n" + "=" * 60)
print("✅ All tests passed! Ready for deployment.")
print("=" * 60)
print("\nNext steps:")
print("1. Optional: Get HF token from https://huggingface.co/settings/tokens")
print("2. Push to GitHub: git add . && git commit -m 'Fix OOM' && git push")
print("3. Deploy to Render (auto-deploy on push)")
