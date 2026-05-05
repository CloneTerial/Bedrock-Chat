import os
import json
import numpy as np
import faiss
from pypdf import PdfReader
import boto3
from dotenv import load_dotenv

load_dotenv()

UPLOAD_DIR = "uploads"
KB_DIR = "knowledge_base"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(KB_DIR, exist_ok=True)

bedrock = boto3.client(
    "bedrock-runtime",
    region_name=os.getenv("AWS_REGION", "us-east-1"),
)

def get_embedding(text: str) -> np.ndarray:
    """Generate vector embeddings using Amazon Titan Text model."""
    try:
        model_id = "amazon.titan-embed-text-v1"
        body = json.dumps({"inputText": text})
        resp = bedrock.invoke_model(
            body=body,
            modelId=model_id,
            accept="application/json",
            contentType="application/json"
        )
        resp_body = json.loads(resp.get("body").read())
        embedding = resp_body.get("embedding")
        return np.array(embedding).astype("float32")
    except Exception as e:
        print(f"Embedding error: {e}")
        return np.zeros(1536).astype("float32")

def index_files(filenames: list[str]):
    """Extract text from files, split into chunks, and update the FAISS vector index."""
    all_chunks = []
    all_metadata = []
    
    print(f"[*] Indexing {len(filenames)} files...")
    
    for fn in filenames:
        path = os.path.join(UPLOAD_DIR, fn)
        text = ""
        if fn.lower().endswith(".pdf"):
            try:
                reader = PdfReader(path)
                for i, page in enumerate(reader.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            except Exception as e:
                print(f"Error reading PDF {fn}: {e}")
        else:
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            except Exception as e:
                print(f"Error reading file {fn}: {e}")
        
        if not text.strip():
            continue
            
        size = 1500
        overlap = 200
        for i in range(0, len(text), size - overlap):
            chunk = text[i:i + size]
            all_chunks.append(chunk)
            all_metadata.append({"filename": fn, "text": chunk})
            
    if not all_chunks:
        return
        
    embeddings = []
    for i, c in enumerate(all_chunks):
        embeddings.append(get_embedding(c))
            
    emp_np = np.stack(embeddings)
    dim = emp_np.shape[1]
    index_path = os.path.join(KB_DIR, "index.faiss")
    meta_path = os.path.join(KB_DIR, "metadata.json")
    
    if os.path.exists(index_path):
        index = faiss.read_index(index_path)
        with open(meta_path, "r") as f:
            old_meta = json.load(f)
        all_metadata = old_meta + all_metadata
    else:
        index = faiss.IndexFlatL2(dim)
        
    index.add(emp_np)
    faiss.write_index(index, index_path)
    with open(meta_path, "w") as f:
        json.dump(all_metadata, f, indent=2)
    print("[+] Indexing complete!")
