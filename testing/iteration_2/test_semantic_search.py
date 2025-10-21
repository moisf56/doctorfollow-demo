"""
Test semantic search with queries relevant to the actual PDF content
PDF: Nelson Essentials of Pediatrics pages 233-282 (Fetal and Neonatal Medicine)

Based on actual content:
- Neonatal resuscitation (cardiac massage, ventilation)
- Fetal circulation (ductus arteriosus)
- Hyperthyroidism in newborns
- Pulmonary hypertension (PPHN)
- Apnea of prematurity
- Meconium aspiration
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from config import settings
from pgvector_store import PgVectorStore


def test_queries():
    """Test with neonatal medicine queries from actual PDF topics"""

    # Initialize pgvector store
    print("Connecting to pgvector...")
    store = PgVectorStore(
        connection_string=settings.get_postgres_url(),
        table_name=settings.PGVECTOR_TABLE,
        embedding_model=settings.EMBEDDING_MODEL,
        embedding_dimension=settings.EMBEDDING_DIMENSION
    )

    # Test queries based on ACTUAL PDF content
    test_cases = [
        {
            "turkish": "Yenidoganlarda kalp masaji nasil yapilir?",
            "english": "How is cardiac massage performed in newborns?",
            "topic": "Neonatal cardiac massage",
            "expected_page": "~10 (mentions cardiac massage, 120 compressions/min)"
        },
        {
            "turkish": "Patent duktus arteriosus nedir?",
            "english": "What is patent ductus arteriosus?",
            "topic": "Ductus arteriosus",
            "expected_page": "~5 (mentions ductus arteriosus in fetal circulation)"
        },
        {
            "turkish": "Yenidoganlarda hipertiroidizm belirtileri",
            "english": "Symptoms of hyperthyroidism in newborns",
            "topic": "Neonatal hyperthyroidism",
            "expected_page": "~20 (Graves disease, thyroid-stimulating antibodies)"
        },
        {
            "turkish": "Prematüre bebeklerde apne tedavisi",
            "english": "Treatment of apnea in premature infants",
            "topic": "Apnea of prematurity",
            "expected_page": "~30 (APNEA OF PREMATURITY section)"
        },
        {
            "turkish": "Yenidoganda pulmoner hipertansiyon",
            "english": "Pulmonary hypertension in newborns",
            "topic": "PPHN",
            "expected_page": "~30 (PRIMARY PULMONARY HYPERTENSION)"
        },
        {
            "turkish": "Mekonyum aspirasyonu nedir?",
            "english": "What is meconium aspiration?",
            "topic": "Meconium aspiration",
            "expected_page": "~30 (meconium aspiration, vocal cords suctioning)"
        }
    ]

    print("\n" + "="*80)
    print("SEMANTIC SEARCH TEST - Multilingual E5-Small")
    print("Testing Turkish vs English queries on Neonatal Medicine PDF")
    print("="*80)

    for i, test in enumerate(test_cases, 1):
        print("\n" + "="*80)
        print(f"TEST {i}/{len(test_cases)}: {test['topic']}")
        print("="*80)
        print(f"Expected: {test['expected_page']}")

        # Turkish query
        print(f"\nTurkish Query: {test['turkish']}")
        results_tr = store.search(test['turkish'], top_k=3)

        print("\nTop 3 Results (Turkish):")
        for j, result in enumerate(results_tr, 1):
            print(f"\n  {j}. Similarity: {result.score:.3f} | Page: {result.page_number}")
            print(f"     {result.text[:150]}...")

        # English query
        print(f"\nEnglish Query: {test['english']}")
        results_en = store.search(test['english'], top_k=3)

        print("\nTop 3 Results (English):")
        for j, result in enumerate(results_en, 1):
            print(f"\n  {j}. Similarity: {result.score:.3f} | Page: {result.page_number}")
            print(f"     {result.text[:150]}...")

        # Compare scores
        avg_tr = sum(r.score for r in results_tr) / len(results_tr) if results_tr else 0
        avg_en = sum(r.score for r in results_en) / len(results_en) if results_en else 0

        print(f"\nAverage Similarity Scores:")
        print(f"  Turkish: {avg_tr:.3f}")
        print(f"  English: {avg_en:.3f}")
        if avg_tr > 0:
            diff_pct = ((avg_en - avg_tr) / avg_tr * 100)
            print(f"  Gap: {(avg_en - avg_tr):.3f} ({diff_pct:+.1f}%)")

            # Evaluation
            if avg_tr > 0.75:
                print("  Evaluation: EXCELLENT Turkish retrieval!")
            elif avg_tr > 0.65:
                print("  Evaluation: GOOD Turkish retrieval")
            elif avg_tr > 0.50:
                print("  Evaluation: MODERATE Turkish retrieval")
            else:
                print("  Evaluation: POOR Turkish retrieval")

    store.close()

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print("\nKey Insights:")
    print("- High Turkish scores (>0.7) = multilingual embeddings working well")
    print("- Small gap (<15%) = good cross-lingual performance")
    print("- Correct pages retrieved = semantic understanding successful")


if __name__ == "__main__":
    test_queries()
