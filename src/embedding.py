from sentence_transformers import SentenceTransformer

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


def create_embedding(text: str):
    embedding = model.encode(text)
    return embedding

if __name__ == "__main__":
    text = "An ALU performs arithmetic and logical operations."

    embedding = create_embedding(text)

    print("Embedding created")
    print("Number of values:", len(embedding))