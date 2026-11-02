
from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PyMuPDFLoader,
    Docx2txtLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from uuid import uuid4


def ingest_spec(
    file_path: str,
) :
    """Load a specification and split it into parent and child chunks."""

    if file_path.endswith(".pdf"):
        loader = PyMuPDFLoader(file_path)
    elif file_path.endswith(".docx"):
        loader = Docx2txtLoader(file_path)
    else:
        raise ValueError("Unsupported file type")

    docs = loader.load()

    parent_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", ". ", " ", ""],
        chunk_size=2000,
        chunk_overlap=200,
        length_function=len,
    )

    parents = parent_splitter.split_documents(docs)

    child_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", ". ", " ", ""],
        chunk_size=700,
        chunk_overlap=100,
        length_function=len,
    )
    children: list[Document] = []
    for parent_id, parent in enumerate(parents):
        child_chunks = child_splitter.split_documents([parent])

        for child in child_chunks:
            child.metadata = child.metadata.copy()
            child.metadata["parent_id"] = parent_id
            children.append(child)

    return parents, children