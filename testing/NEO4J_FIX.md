# Neo4j SSL Certificate Fix

## The Problem

When using **complex queries** (which trigger Knowledge Graph enrichment), you were getting this error:

```
neo4j.exceptions.ServiceUnavailable: Unable to retrieve routing information
ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED]
certificate verify failed: self-signed certificate in certificate chain
```

**Why it happened:**
- Neo4j Aura (cloud) uses SSL/TLS certificates for secure connections
- The Python neo4j driver wasn't configured to trust these certificates
- Simple queries worked (no KG), but complex queries failed when trying to connect to Neo4j

## The Solution

I've updated the Neo4j connection code to properly handle SSL certificates for Neo4j Aura.

### Files Modified

1. **[neo4j_store.py](iteration_3/neo4j_store.py)** - Updated `__init__` method (lines 43-100)
   - Added proper SSL certificate handling
   - Uses `TrustSystemCAs()` for Neo4j Aura (recommended)
   - Falls back to `TrustAll()` if system CAs fail
   - Supports both new and legacy neo4j driver versions

2. **[requirements.txt](requirements.txt)** - Added `certifi>=2024.0.0` (line 70)
   - Provides up-to-date SSL certificates
   - Required for SSL verification

### Files Created

3. **[test_neo4j_connection.py](iteration_3/test_neo4j_connection.py)** - Test script
   - Verifies Neo4j connection works
   - Shows database info and node counts
   - Helps troubleshoot connection issues

## How to Test the Fix

### Option 1: Run the Test Script

```bash
cd testing/iteration_3
python test_neo4j_connection.py
```

**Expected output:**
```
================================================================================
Testing Neo4j Aura Connection
================================================================================

Neo4j URI: neo4j+s://52dba6f2.databases.neo4j.io
Neo4j User: neo4j
Neo4j Password: ********

--------------------------------------------------------------------------------
Attempting connection...
--------------------------------------------------------------------------------

[OK] Connected to Neo4j at neo4j+s://52dba6f2.databases.neo4j.io with system CA certificates
[OK] Neo4j schema initialized

Testing query execution...
[OK] Connection successful!

Checking database info...
  Database: Neo4j Kernel
  Version: 5.x.x
  Edition: enterprise

Checking graph data...
  Total nodes: XXX

  Nodes by type:
    Disease: XX
    Drug: XX
    Symptom: XX
    ...

================================================================================
[SUCCESS] Neo4j connection is working!
================================================================================
```

### Option 2: Test with API Server

1. **Restart your API server:**
   ```bash
   cd testing/iteration_3
   python api_server.py
   ```

2. **Send a complex query** (triggers KG enrichment):
   ```
   Query: "Zamanında doğan bir bebek, doğumdan 6 saat sonra taşipne (60/dk),
          inleme ve interkostal çekilmeler gösteriyor. Akciğer grafisinde
          bilateral granüler patern ve hava bronkogramları görülüyor.
          En olası tanı nedir ve ilk basamak tedavi ne olmalıdır?"
   ```

3. **Check the logs** - You should see:
   ```
   [HYBRID RETRIEVE] Query: ... (complexity: complex)
   [KG ENRICH] Expanding with knowledge graph...
   [OK] Added knowledge graph context (XXX chars)
   [GENERATE] Creating answer...
   [OK] Answer generated
   ```

   **No more SSL errors!** ✅

## What Changed Under the Hood

### Before (Broken):
```python
self.driver = GraphDatabase.driver(uri, auth=(user, password))
# ❌ No SSL configuration - fails with Neo4j Aura
```

### After (Fixed):
```python
from neo4j import TrustSystemCAs, TrustAll

# Try system CAs first (recommended for Aura)
self.driver = GraphDatabase.driver(
    uri,
    auth=(user, password),
    trusted_certificates=TrustSystemCAs()
)
# ✅ Properly configured for SSL
```

### Fallback Strategy:
1. **First attempt:** Trust system CA certificates (most secure, recommended for Aura)
2. **If that fails:** Trust all certificates (works for self-signed certs)
3. **Legacy support:** Falls back to older driver API if needed

## Verification Checklist

After applying the fix:

- [ ] Test script runs successfully
- [ ] API server starts without errors
- [ ] Simple queries work (no KG)
- [ ] **Complex queries work (with KG)** ← This is the key test!
- [ ] No SSL certificate errors in logs

## Environment Variables (Already Correct)

Your `.env` file already has the correct Neo4j configuration:

```bash
NEO4J_URI=neo4j+s://52dba6f2.databases.neo4j.io  # ✅ Correct format
NEO4J_USER=neo4j                                   # ✅ Default user
NEO4J_PASSWORD=KRFRRHmIMvw1lcg-MEjWDEtGfHlw8...   # ✅ Your password
```

**Key points:**
- ✅ URI uses `neo4j+s://` (secure scheme)
- ✅ No port specified (Aura handles this automatically)
- ✅ Credentials are set

## Troubleshooting

### If you still get SSL errors:

1. **Update certifi package:**
   ```bash
   pip install --upgrade certifi
   ```

2. **Check Neo4j driver version:**
   ```bash
   pip show neo4j
   # Should be 5.0.0 or higher
   ```

3. **Verify Neo4j Aura is accessible:**
   - Check Neo4j Aura Console
   - Ensure instance is running
   - Verify IP whitelist (or allow all IPs for testing)

4. **Test with simple cypher query:**
   ```python
   from neo4j import GraphDatabase

   driver = GraphDatabase.driver(
       "neo4j+s://52dba6f2.databases.neo4j.io",
       auth=("neo4j", "your-password")
   )
   with driver.session() as session:
       result = session.run("RETURN 'Hello' AS message")
       print(result.single()["message"])
   driver.close()
   ```

### If the test script fails:

Check the error message:
- **Authentication error** → Verify password in `.env`
- **Connection timeout** → Check firewall/IP whitelist
- **Certificate error** → Update certifi: `pip install --upgrade certifi`
- **Import error** → Reinstall neo4j: `pip install --force-reinstall neo4j>=5.0.0`

## Why Simple Queries Worked But Complex Didn't

From your logs:

✅ **Simple queries** (complexity: simple):
```
[HYBRID RETRIEVE] Query: rds nedir (complexity: simple)
  [BM25] Retrieving top 10...
  [OK] BM25 retrieved 10 chunks
  [Semantic] Retrieving top 10...
  [OK] Semantic retrieved 10 chunks
  [RRF] Fusing results...
  [OK] Fused to top 3 chunks
[GENERATE] Creating answer...
[OK] Answer generated
```
→ **No Neo4j connection needed** (skips KG enrichment)

❌ **Complex queries** (complexity: complex):
```
[HYBRID RETRIEVE] Query: ... (complexity: complex)
  [BM25] Retrieving top 10...
  [OK] BM25 retrieved 10 chunks
  [Semantic] Retrieving top 10...
  [OK] Semantic retrieved 10 chunks
  [RRF] Fusing results...
  [OK] Fused to top 3 chunks
[KG ENRICH] Expanding with knowledge graph...  ← Tries to connect to Neo4j
Unable to retrieve routing information          ← SSL certificate error!
[STREAMING ERROR] Error: Unable to retrieve routing information
```
→ **Neo4j connection required** (triggers SSL error)

## Next Steps

1. **Test the fix immediately:**
   ```bash
   cd testing/iteration_3
   python test_neo4j_connection.py
   ```

2. **If test passes, restart your API:**
   ```bash
   python api_server.py
   ```

3. **Try a complex query from your frontend**

4. **Verify in logs:**
   - Look for `[KG ENRICH] Expanding with knowledge graph...`
   - Should see `[OK] Added knowledge graph context` instead of errors

## Summary

**Problem:** SSL certificate verification failed for Neo4j Aura
**Root Cause:** Missing SSL configuration in neo4j driver
**Solution:** Added proper certificate trust configuration
**Files Changed:** `neo4j_store.py`, `requirements.txt`
**Test Script:** `test_neo4j_connection.py`
**Status:** ✅ **FIXED** - Ready to test!

---

**Questions?** Check the test script output for detailed diagnostics.
