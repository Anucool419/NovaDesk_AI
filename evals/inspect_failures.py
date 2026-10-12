import pandas as pd

df = pd.read_csv("evals/reports/ablation_rag_only_report.csv")

# Sort by answer_correctness and context_recall ascending to find the worst failures
worst_rows = df.sort_values(by=["answer_correctness", "context_recall"], ascending=True).head(5)

for idx, row in worst_rows.iterrows():
    print("==========================================")
    print(f"ID: {row['id']} | Bucket: {row['bucket']} | Mode: {row['rag_mode'].upper()}")
    print(f"Recall: {row['context_recall']:.3f} | Faithfulness: {row['faithfulness']:.3f} | Correctness: {row['answer_correctness']:.3f}")
    print(f"Question:     {row['user_input'] if 'user_input' in row else row['question']}")
    print(f"Bot Answer:   {row['response'] if 'response' in row else row['answer']}")
    print(f"Ground Truth: {row['reference'] if 'reference' in row else row['ground_truth']}")
    print(f"Retrieved:    {str(row['retrieved_contexts'] if 'retrieved_contexts' in row else row['contexts'])[:300]}...")