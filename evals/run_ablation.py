import os
import sys
import json
import time
import uuid
import pandas as pd
from datasets import Dataset
from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI
from langchain_community.callbacks import get_openai_callback

from ragas import evaluate
from ragas.run_config import RunConfig
from ragas.embeddings import OpenAIEmbeddings as RagasOpenAIEmbeddings
from ragas.llms import llm_factory
from ragas.metrics import (
    AnswerCorrectness,
    ContextPrecision,
    ContextRecall,
    Faithfulness,
)

# Add project root to sys.path so we can import your bot modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

load_dotenv()

# =====================================================================
# TODO: CHECK YOUR IMPORTS HERE
# Adjust 'graph' and 'nodes' to match the exact filenames in NovaDesk_AI
# =====================================================================
from graph import agent_app
from rag2 import hyde_rewriter_node, rag_execution_node

# Paths
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
GOLDEN_DATASET_PATH = os.path.join(EVAL_DIR, "golden_dataset.json")
REPORTS_DIR = os.path.join(EVAL_DIR, "reports")

# =====================================================================
# TEST SCOPE TOGGLE:
#   "rag_only"   -> Calls hyde_rewriter_node + rag_execution_node directly.
#                   Best for pure Naive vs Rewriter vs HyDE comparison
#                   (skips Guardrail, Router, and Memory Extractor overhead).
#   "full_graph" -> Calls agent_app.invoke(). Tests the entire bot including
#                   Guardrail and Router accuracy.
# =====================================================================
EVAL_SCOPE = "rag_only"  # Change to "full_graph" once pure RAG is verified!

# 1. Initialize your verified RAGAS Judge Setup
openai_client = OpenAI()
evaluator_llm = llm_factory("gpt-4o-mini", client=openai_client)
evaluator_embeddings = RagasOpenAIEmbeddings(
    client=AsyncOpenAI(),
    model="text-embedding-3-small",
)


def execute_single_query(question: str, mode: str) -> tuple[str, list[str]]:
    """
    Executes a single question in the specified rag_mode ('naive', 'rewriter', 'hyde')
    and returns (generated_answer, retrieved_chunks_list).
    """
    config = {
        "configurable": {
            "thread_id": f"eval_{mode}_{uuid.uuid4()}",
            "user_id": "eval_benchmark_guest",
            "rag_mode": mode,
        }
    }

    if EVAL_SCOPE == "rag_only":
        # Direct node execution: isolates RAG latency/tokens from Router & Memory nodes
        state = {"user_query": question, "messages": [("user", question)]}
        rewrite_update = hyde_rewriter_node(state, config)
        state.update(rewrite_update)
        rag_update = rag_execution_node(state)
        
        ans = rag_update["messages"][-1].content
        ctxs = rag_update.get("retrieved_contexts") or ["No context retrieved."]
        return ans, ctxs

    else:
        # Full End-to-End Graph execution
        final_state = agent_app.invoke(
            {"user_query": question, "messages": [("user", question)]},
            config=config,
        )
        messages = final_state.get("messages", [])
        # Handle both tuple messages and AIMessage objects
        last_msg = messages[-1] if messages else ""
        ans = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        ctxs = final_state.get("retrieved_contexts") or ["No context retrieved (Misrouted or Blocked)."]
        return ans, ctxs


def run_ablation_for_mode(mode: str, test_cases: list[dict]) -> tuple[pd.DataFrame, dict]:
    questions, answers, contexts, ground_truths = [], [], [], []
    ids, buckets, latencies, token_counts, costs = [], [], [], [], []

    print(f"\n=======================================================")
    print(f"🚀 RUNNING INFERENCE FOR MODE: [{mode.upper()}] (Scope: {EVAL_SCOPE})")
    print(f"=======================================================")

    for idx, case in enumerate(test_cases, start=1):
        q_id = case.get("id", f"q_{idx}")
        bucket = case.get("bucket", "unbucketed")
        q = case["question"]
        gt = case["ground_truth"]

        print(f"  [{idx:02d}/{len(test_cases):02d}] ({q_id}) {q[:65]}...")

        start_time = time.perf_counter()
        with get_openai_callback() as cb:
            ans, ctxs = execute_single_query(q, mode)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        ids.append(q_id)
        buckets.append(bucket)
        questions.append(q)
        answers.append(ans)
        contexts.append(ctxs)
        ground_truths.append(gt)

        latencies.append(round(elapsed_ms, 1))
        token_counts.append(cb.total_tokens)
        costs.append(cb.total_cost)

    # Format for RAGAS
    hf_dataset = Dataset.from_dict({
        "question": questions,
        "contexts": contexts,
        "answer": answers,
        "ground_truth": ground_truths,
    })

    print(f"\n📊 Evaluating [{mode.upper()}] with RAGAS...")
    result = evaluate(
        dataset=hf_dataset,
        metrics=[
            ContextPrecision(llm=evaluator_llm),
            ContextRecall(llm=evaluator_llm),
            Faithfulness(llm=evaluator_llm),
            AnswerCorrectness(llm=evaluator_llm, embeddings=evaluator_embeddings),
        ],
        llm=evaluator_llm,
        embeddings=evaluator_embeddings,
        run_config=RunConfig(
            timeout=300,
            max_retries=5,
            max_wait=60,
            max_workers=2,
        ),
        batch_size=1,
    )

    df = result.to_pandas()
    df["id"] = ids
    df["bucket"] = buckets
    df["rag_mode"] = mode
    df["latency_ms"] = latencies
    df["total_tokens"] = token_counts
    df["cost_usd"] = costs

    summary = {
        "Mode": mode.upper(),
        "Context Precision": round(df["context_precision"].mean(), 4),
        "Context Recall": round(df["context_recall"].mean(), 4),
        "Faithfulness": round(df["faithfulness"].mean(), 4),
        "Answer Correctness": round(df["answer_correctness"].mean(), 4),
        "Avg Latency (ms)": round(sum(latencies) / len(latencies), 1),
        "Avg Tokens": round(sum(token_counts) / len(token_counts), 1),
        "Total Cost ($)": round(sum(costs), 5),
    }

    return df, summary


if __name__ == "__main__":
    os.makedirs(REPORTS_DIR, exist_ok=True)

    with open(GOLDEN_DATASET_PATH, "r", encoding="utf-8") as f:
        golden_cases = json.load(f)

    # Smoke Test Tip: Uncomment the next line to test on just 2 questions first!
    # golden_cases = golden_cases[:2]

    all_dfs = []
    summaries = []

    for mode in ["naive", "rewriter", "hyde"]:
        df_mode, summary_mode = run_ablation_for_mode(mode, golden_cases)
        all_dfs.append(df_mode)
        summaries.append(summary_mode)

    # 1. Print Overall Mode Comparison
    comparison_df = pd.DataFrame(summaries)
    print("\n================ OVERALL ABLATION SUMMARY ================")
    print(comparison_df.to_string(index=False))

    # 2. Print Bucket-by-Bucket Breakdown
    full_results_df = pd.concat(all_dfs, ignore_index=True)
    print("\n================ BUCKET-LEVEL BREAKDOWN ================")
    bucket_summary = (
        full_results_df.groupby(["bucket", "rag_mode"])[
            ["context_precision", "context_recall", "faithfulness", "answer_correctness", "latency_ms", "total_tokens"]
        ]
        .mean()
        .round(3)
    )
    print(bucket_summary.to_string())

    # 3. Save Full CSV Report
    csv_path = os.path.join(REPORTS_DIR, f"ablation_{EVAL_SCOPE}_report.csv")
    full_results_df.to_csv(csv_path, index=False)
    print(f"\n✅ Detailed row-by-row report saved to: {csv_path}")