# Source References Display Fix

## The Problem

When displaying references in the frontend, the raw source chunks were showing unformatted text that looked weird:

```
Source 1 - Page 44
85% 9-12 wk, 50% 13-20 wk, 16% Virus may be present in infant's throat for 1 yr Prevention: vaccine Intrauterine growth restriction, microcephaly, microphthalmia, cataracts, glaucoma, "salt and pepper" chorioretinitis, hepatosplenomegaly, jaundice, PDA, deafness, blueberry muffin rash, anemia, thrombocytopenia, leukopenia, metaphyseal lucencies, B-cell and T-cell deficiency
```

This happens because:
1. The chunks are stored as-is from the PDF (tables, lists, compressed text)
2. The frontend was displaying the full raw `text` field
3. No formatting or preview was generated

## The Solution

Added a `snippet` field to each source that provides a clean, short preview:

### Backend Changes

**File: `api_server.py`**

1. **Updated Source Model** (line 138):
   ```python
   class Source(BaseModel):
       chunk_id: str
       text: str              # Full raw text (for LLM)
       page_number: int
       snippet: str           # NEW: Clean 150-char preview (for display)
       rrf_score: Optional[float] = None
       bm25_score: Optional[float] = None
       semantic_score: Optional[float] = None
   ```

2. **Generate Snippets** (lines 437-456):
   ```python
   # Create a clean snippet (first 150 chars, clean whitespace)
   text = src["text"]
   snippet = text[:150].strip()
   snippet = ' '.join(snippet.split())  # Clean whitespace
   if len(text) > 150:
       snippet += "..."
   ```

3. **Applied to both endpoints**:
   - `/chat` endpoint (non-streaming)
   - `/chat/stream` endpoint (streaming)

### Frontend Changes Needed

Update your frontend to use the `snippet` field instead of `text`:

**Before:**
```typescript
<div className="source">
  <h4>Source {i} - Page {source.page_number}</h4>
  <p>{source.text}</p>  {/* ❌ Shows raw, unformatted text */}
</div>
```

**After:**
```typescript
<div className="source">
  <h4>Source {i} - Page {source.page_number}</h4>
  <p>{source.snippet}</p>  {/* ✅ Shows clean preview */}
  {/* Optionally show full text in expandable section */}
  {showFull && <pre className="full-text">{source.text}</pre>}
</div>
```

## Expected Result

**Before:**
```
Source 1 - Page 44
85% 9-12 wk, 50% 13-20 wk, 16% Virus may be present in infant's throat for 1 yr Prevention: vaccine Intrauterine growth restriction, microcephaly...
```

**After:**
```
Source 1 - Page 44
85% 9-12 wk, 50% 13-20 wk, 16% Virus may be present in infant's throat for 1 yr Prevention: vaccine Intrauterine growth restriction...
```

Still not perfect (because source data is compressed), but much cleaner!

## Better Alternative: Use LLM-Generated References

The LLM already generates a clean "References:" section in the answer. You can:

**Option A: Show only LLM references** (recommended)
- Parse the answer for the "References:" section
- Display that instead of raw sources
- Hide the raw sources entirely

**Option B: Show both** (current approach)
- LLM references in answer (formatted, contextual)
- Source snippets below (for verification, show/hide)

## Example API Response

```json
{
  "query": "What is RDS treatment?",
  "answer": "...\n\n---\nReferences:\n[Source 1] - Page 10: Discusses RDS pathophysiology...\n[Source 2] - Page 15: Covers surfactant therapy...",
  "sources": [
    {
      "chunk_id": "chunk_123",
      "text": "Very long unformatted text from PDF table...",
      "snippet": "Respiratory distress syndrome (RDS) treatment includes surfactant therapy, mechanical ventilation...",
      "page_number": 10,
      "rrf_score": 0.95
    }
  ]
}
```

## To Apply This Fix

1. **Restart backend** (api_server.py has been updated)
2. **Update frontend** to use `source.snippet` instead of `source.text`
3. **Test** - sources should now show cleaner previews

## Notes

- The `text` field still contains the full raw text (needed for LLM context)
- The `snippet` field is only for display purposes
- Snippets are limited to 150 characters
- Whitespace is cleaned (removes newlines, extra spaces)

---

**Status**: ✅ Backend fix applied, waiting for frontend update
