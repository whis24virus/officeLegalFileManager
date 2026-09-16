import chromadb
import numpy as np

client = chromadb.PersistentClient(path="data/vectors")
collection = client.get_or_create_collection("test_query")
if collection.count() == 0:
    collection.add(embeddings=[np.zeros(1024).tolist()], ids=["1"])

print("Querying...")
try:
    results = collection.query(
        query_embeddings=[np.zeros(1024).tolist()],
        n_results=1,
        include=["distances", "metadatas", "documents"]
    )
    print("Results:", results)
except Exception as e:
    import traceback
    traceback.print_exc()
