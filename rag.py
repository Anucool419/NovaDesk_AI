# rag.py
import os
from langchain_community.document_loaders import PyPDFLoader, TextLoader, CSVLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Make sure your OPENAI_API_KEY is set in your environment or add it here temporarily
# os.environ["OPENAI_API_KEY"] = "your-api-key-here"
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
os.environ["OPENAI_API_KEY"]=os.getenv("OPENAI_API_KEY")



# 1. Load the unstructured text document
#loader = TextLoader("novotel_policies.txt")
loader = PyPDFLoader("Novotel_Hotel_Policies_Mock.pdf")
csv_loader=CSVLoader("novotel_hotel_faqs_policy_based.csv")
pdf_docs = loader.load()
csv_docs=csv_loader.load()
all_docs=csv_docs+pdf_docs
# 2. Chunk the text into smaller, digestible pieces
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
splits = text_splitter.split_documents(all_docs)

# 3. Create the vector store using OpenAI Embeddings
vectorstore = FAISS.from_documents(splits, OpenAIEmbeddings())
#retriever = vectorstore.as_retriever(search_kwargs={"k": 5}) 
#new retriever with MMR instead of above
retriever = vectorstore.as_retriever(
    search_type="mmr",
    search_kwargs={
        "k": 6,            # Captures both FAQ snippets and full PDF sections
        "fetch_k": 20,     # Evaluates top 20 candidates for topic diversity
        "lambda_mult": 0.6 # Stronger diversity weighting for multi-part questions
    }
)

# THE csv and pdf speak of similar things that is FAQs and instructions in pdf are similar and hence the retriever is confused when asked a question as to which part to retrieve when it gets very similar chunks. 
# Hence, we increase from top-k:5 to top-k:10 so we expand our scope for retrieval, and we can later choose to go for csv for quick operational facts (prices, hours) and 
# PDF chunks for strictly for long-form rules (behavior, legal disclaimers). If they overlap, delete the redundancy from the PDF chunks before embedding.

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
)

# 4. Wrap the retriever in a LangChain tool
@tool
def search_hotel_policies(query: str) -> str:
    """
    Use this tool to answer guest questions about hotel policies, 
    such as pool hours, pet rules, check-in times, or cancellation policies.
    """
    results = retriever.invoke(query)
    # Combine the retrieved chunks into a single text string for the LLM
    return "\n\n".join(doc.page_content for doc in results)


policy_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a precise and professional hotel customer support agent. "
        "Answer the guest's question using ONLY the provided hotel policy context. "
        "CRITICAL INSTRUCTION: You must always state the exact fees, prices, times, and rules mentioned in the context. Do not generalize or abstract numbers. If numbers are not provided then just provide information provided don't create numbers."
        "If the context does not contain the answer, say 'I do not know.'\n\n"
        "Context:\n{context}",
    ),
    ("human", "{question}"),
])

policy_chain = policy_prompt | llm | StrOutputParser()


def answer_policy_question(question: str) -> str:
    """Retrieve relevant policy text and use the LLM to answer the question."""
    context = search_hotel_policies.invoke(question)
    # ADD THIS LINE TO DEBUG:
    print(f"\n[DEBUG - RETRIEVED CONTEXT]:\n{context}\n")
    return policy_chain.invoke({"context": context, "question": question})

# Quick local test
if __name__ == "__main__":
    print("TESTING RAG TOOL.....")
    print(answer_policy_question("What are the smoking policies?"))
    print("\n--- Testing PDF Retrieval ---")
    #print(answer_policy_question("What are the responsibilities of a good guest?"))
    print(answer_policy_question(("What is the policy on guest conduct and behavior?")))
        
    
    print("\n--- Testing CSV Retrieval ---")
    print(answer_policy_question("Do you have vegan breakfast?"))