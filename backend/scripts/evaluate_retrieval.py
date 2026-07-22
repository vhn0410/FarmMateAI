import sys
import json
import time
import argparse
from pathlib import Path
from typing import List, Dict

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(str(Path(__file__).resolve().parent.parent))

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever

from app.core.config import settings
from app.application.documents.chunking.parent_document_chunker import ParentDocumentChunker
from app.infrastructure.vector_store.pgvector_provider import PGVectorProvider

LLM = ChatOpenAI(model="gpt-4o-mini", api_key=settings.openai_api_key, base_url=settings.openai_api_base, temperature=0)

def evaluate_retrieved_chunks(question: str, ground_truth: str, chunks: List[str]) -> Dict[str, float]:
    context = "\n\n".join([f"Chunk {i+1}:\n{c}" for i, c in enumerate(chunks)])
    
    # 1. Evaluate Precision (Is the context relevant?)
    precision_prompt = ChatPromptTemplate.from_messages([
        ("system", "Evaluate how relevant the provided context is to the question. Does the context contain enough information to answer the question? Respond with JSON: {{\"score\": 1}} if it directly answers the question, {{\"score\": 0}} if it is completely off-topic, or {{\"score\": 0.5}} if it is relevant but does not directly answer the question. Return only JSON."),
        ("user", "Question: {question}\nContext:\n{context}")
    ])
    p_resp = (precision_prompt | LLM).invoke({"question": question, "context": context})
    p_content = p_resp.content.strip()
    if p_content.startswith("```json"): p_content = p_content[7:-3]
    elif p_content.startswith("```"): p_content = p_content[3:-3]
    try:
        precision_score = float(json.loads(p_content).get("score", 0))
    except:
        precision_score = 0
        
    # 2. Evaluate Recall (Does the context contain ENOUGH information to answer?)
    recall_prompt = ChatPromptTemplate.from_messages([
        ("system", "Compare the provided context with the reference answer. Does the context cover enough of the reference answer's main points? Respond with JSON: {{\"score\": 1}} if it covers all main points, {{\"score\": 0.5}} if it covers only part of them, or {{\"score\": 0}} if it covers none. Return only JSON."),
        ("user", "Reference answer:\n{ground_truth}\n\nContext:\n{context}")
    ])
    r_resp = (recall_prompt | LLM).invoke({"ground_truth": ground_truth, "context": context})
    r_content = r_resp.content.strip()
    if r_content.startswith("```json"): r_content = r_content[7:-3]
    elif r_content.startswith("```"): r_content = r_content[3:-3]
    try:
        recall_score = float(json.loads(r_content).get("score", 0))
    except:
        recall_score = 0
        
    return {"precision": precision_score, "recall": recall_score}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Markdown filename inside the data/knowledge_base/processed/ directory")
    args = parser.parse_args()
    
    base_dir = Path("data/knowledge_base/processed")
    file_path = base_dir / args.file
    if not file_path.exists():
        if (base_dir / f"{args.file}.md").exists():
            file_path = base_dir / f"{args.file}.md"
        else:
            print(f"File {file_path} does not exist.")
            sys.exit(1)
            
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
        
    gold_qa_file = Path("evaluate/gold_qa") / f"{Path(args.file).stem}_gold_qa.json"
    if not gold_qa_file.exists():
        print(f"The Gold QA set is missing: {gold_qa_file}. Generate it first.")
        sys.exit(1)
        
    with open(gold_qa_file, "r", encoding="utf-8") as f:
        qa_pairs = json.load(f)
        
    print(f"Loaded {len(qa_pairs)} evaluation questions.")
    
    # 1. Chunking the document using Parent Document Chunker
    print("Chunking the text using Parent Document Chunking...")
    chunker = ParentDocumentChunker()
    docs = chunker.chunk(text, source=args.file)
    print(f"Created {len(docs)} chunks as input for the retrievers.")
    
    # 2. Setup Retrievers
    print("Initializing the local retrievers...")
    
    # A. Vector Retriever
    embeddings = HuggingFaceEmbeddings(
        model_name=settings.huggingface_embedding_model,
        model_kwargs={'device': 'cpu'}, 
        encode_kwargs={'normalize_embeddings': True}
    )
    vectorstore = FAISS.from_documents(docs, embeddings)
    vector_retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    
    # B. Keyword Retriever (BM25)
    keyword_retriever = BM25Retriever.from_documents(docs)
    keyword_retriever.k = 3
    
    # C. Hybrid Retriever (Ensemble RRF)
    hybrid_retriever = EnsembleRetriever(
        retrievers=[vector_retriever, keyword_retriever],
        weights=[0.5, 0.5]
    )
    
    # D. Production Retriever (PGVector + Hybrid + CrossEncoder)
    print("Initializing the production retriever (PostgreSQL)...")
    pg_provider = PGVectorProvider()
    prod_retriever = pg_provider.get_parent_document_retriever(file_ids=[args.file, f"{args.file}.md"])
    
    retrievers_to_test = {
        "Pure Vector Search (FAISS)": vector_retriever,
        "Pure Keyword Search (BM25)": keyword_retriever,
        "Hybrid Search (RRF 50/50)": hybrid_retriever,
        "Production Hybrid + Reranker": prod_retriever
    }
    
    results = {}
    
    for name, retriever in retrievers_to_test.items():
        print(f"\n--- Evaluating {name} ---")
        
        total_precision = 0
        total_recall = 0
        start_time = time.time()
        
        for qa in qa_pairs:
            q = qa['question']
            a = qa['answer']
            
            # Retrieval Step
            retrieved_docs = retriever.invoke(q)
            # EnsembleRetriever might return > 3 docs depending on overlap, so we slice top 3
            retrieved_docs = retrieved_docs[:3] 
            retrieved_texts = [d.page_content for d in retrieved_docs]
            
            # Evaluation Step
            try:
                scores = evaluate_retrieved_chunks(q, a, retrieved_texts)
                total_precision += scores['precision']
                total_recall += scores['recall']
            except Exception as e:
                print(f"Error evaluating question: {e}")
                # Wait longer on error (e.g. rate limit)
                time.sleep(5)
                try:
                    scores = evaluate_retrieved_chunks(q, a, retrieved_texts)
                    total_precision += scores['precision']
                    total_recall += scores['recall']
                except:
                    pass
                
            # Avoid OpenAI rate limits (429)
            time.sleep(1.5)
            
        elapsed_time = time.time() - start_time
        
        avg_precision = total_precision / len(qa_pairs) if qa_pairs else 0
        avg_recall = total_recall / len(qa_pairs) if qa_pairs else 0
        
        results[name] = {
            "Time (s)": round(elapsed_time, 2),
            "Precision": round(avg_precision * 100, 2),
            "Recall": round(avg_recall * 100, 2)
        }
        
    # Write Report
    report_lines = [
        "# Retrieval Methods Evaluation Report",
        f"**File test:** {args.file}",
        f"**Number of questions (Gold QA):** {len(qa_pairs)}",
        "**Chunking method base:** Parent Document Chunking",
        "**Top K retrieve:** 3",
        "",
        "| Retrieval method | Evaluation time (s) | Precision (%) | Recall (%) |",
        "|-----------------------|------------------------|---------------|------------|"
    ]
    
    for name, data in results.items():
        report_lines.append(
            f"| {name} | {data['Time (s)']} | **{data['Precision']}%** | **{data['Recall']}%** |"
        )
        
    report_content = "\n".join(report_lines)
    report_path = Path("evaluate/results/retrieve/retrieval_evaluation_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print(f"\n✅ Report exported to: {report_path.resolve()}")

if __name__ == "__main__":
    main()
