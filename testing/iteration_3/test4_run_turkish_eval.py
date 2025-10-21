"""
Test 4: Turkish Query Evaluation with RAG v3
Tests language detection and cross-lingual medical QA
"""
import sys
from pathlib import Path
import json
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent))

from rag_v3 import MedicalRAGv3


def load_test_queries(file_path: str) -> dict:
    """Load test queries from JSON file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def run_test_query(rag: MedicalRAGv3, query_data: dict) -> dict:
    """
    Run a single test query and collect results

    Args:
        rag: RAG v3 system
        query_data: Query data from test file

    Returns:
        Test result dict
    """
    print("\n" + "="*100)
    print(f"TEST QUERY ID: {query_data['id']}")
    print(f"Category: {query_data['category']}")
    print("="*100)
    print(f"\nQUERY (Turkish): {query_data['query_turkish']}")
    print(f"QUERY (English translation): {query_data['query_english']}")
    print("\n" + "-"*100)

    # Run RAG query
    result = rag.ask(query_data['query_turkish'])

    # Display results
    print("\n[SYSTEM RESPONSE]")
    print("-"*100)
    print(result['answer'])
    print("-"*100)

    print(f"\n[SOURCES USED] ({result['num_sources']} sources)")
    for i, source in enumerate(result['sources'], 1):
        print(f"  {i}. Page {source['page_number']} - RRF: {source['rrf_score']:.4f}")

    if result.get('kg_context'):
        print(f"\n[KNOWLEDGE GRAPH CONTEXT]")
        kg_preview = result['kg_context'][:300] + "..." if len(result['kg_context']) > 300 else result['kg_context']
        print(kg_preview)

    # Collect test result
    test_result = {
        "query_id": query_data['id'],
        "query_turkish": query_data['query_turkish'],
        "query_english": query_data['query_english'],
        "category": query_data['category'],
        "system_answer": result['answer'],
        "expected_answer": query_data['expected_answer_turkish'],
        "num_sources": result['num_sources'],
        "sources": result['sources'],
        "kg_context_length": len(result.get('kg_context', '')),
        "has_kg_context": bool(result.get('kg_context')),
    }

    return test_result


def evaluate_results(test_results: list, test_data: dict) -> dict:
    """
    Evaluate test results

    Args:
        test_results: List of test result dicts
        test_data: Original test data

    Returns:
        Evaluation summary
    """
    evaluation = {
        "total_queries": len(test_results),
        "timestamp": datetime.now().isoformat(),
        "test_name": test_data['test_name'],
        "results": []
    }

    for result in test_results:
        # Manual evaluation criteria (to be filled by human evaluator)
        eval_item = {
            "query_id": result['query_id'],
            "category": result['category'],
            "query": result['query_turkish'],
            "system_answer": result['system_answer'],
            "expected_answer": result['expected_answer'],
            "metrics": {
                "language_correct": None,  # Manual: Is response in Turkish?
                "medically_accurate": None,  # Manual: Is the medical info correct?
                "entities_covered": None,  # Manual: Are key entities mentioned?
                "sources_cited": None,  # Manual: Are sources properly cited?
                "kg_helpful": None,  # Manual: Did KG enrichment help?
                "completeness": None,  # Manual: All parts of question addressed?
            },
            "num_sources": result['num_sources'],
            "has_kg_context": result['has_kg_context'],
        }
        evaluation["results"].append(eval_item)

    return evaluation


def main():
    """Main test execution"""
    print("="*100)
    print("TEST 4: Turkish Clinical Case Evaluation with RAG v3")
    print("="*100)
    print()

    # Load test queries
    test_file = Path(__file__).parent / "test4_turkish_queries.json"
    test_data = load_test_queries(test_file)

    print(f"Test: {test_data['test_name']}")
    print(f"Total queries: {len(test_data['test_queries'])}")
    print(f"Difficulty: {test_data['difficulty_level']}")
    print()

    # Initialize RAG v3
    print("[Initializing] RAG v3 system...")
    rag = MedicalRAGv3()
    print()

    # Run test queries
    test_results = []
    for query_data in test_data['test_queries']:
        try:
            result = run_test_query(rag, query_data)
            test_results.append(result)
        except Exception as e:
            print(f"\n[ERROR] Query {query_data['id']} failed: {e}")
            import traceback
            traceback.print_exc()

    # Evaluate and save results
    print("\n" + "="*100)
    print("GENERATING EVALUATION REPORT")
    print("="*100)

    evaluation = evaluate_results(test_results, test_data)

    # Save evaluation to file
    output_file = Path(__file__).parent / f"test4_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(evaluation, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] Results saved to: {output_file}")
    print(f"\nTotal queries tested: {len(test_results)}")
    print(f"Queries with KG enrichment: {sum(1 for r in test_results if r['has_kg_context'])}")

    print("\n" + "="*100)
    print("TEST 4 COMPLETE")
    print("="*100)
    print("\nNext steps:")
    print("1. Review the generated JSON file for system responses")
    print("2. Manually evaluate each response using the evaluation criteria")
    print("3. Calculate final scores and identify areas for improvement")
    print()


if __name__ == "__main__":
    main()
