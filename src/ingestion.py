
from langchain_community.document_loaders import (
    PyMuPDFLoader,
    Docx2txtLoader,
)

from langchain_text_splitters import RecursiveCharacterTextSplitter


def ingest_spec(file_path: str):
    """
    Load a hardware specification and create parent-child chunks.

    Returns:
        docs: Original documents
        parents: Parent chunks
        children: Child chunks
    """

    suffix = file_path.lower().rsplit(".", 1)[-1] if "." in file_path else ""

    if suffix == "pdf":
        loader = PyMuPDFLoader(file_path)

    elif suffix == "docx":
        loader = Docx2txtLoader(file_path)

    else:
        raise ValueError("Unsupported file type")

    # Load original documents
    docs = loader.load()

    if not docs:
        raise ValueError("Specification document is empty")

    # Parent chunking
    parent_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", ".", " "],
        chunk_size=3000,
        chunk_overlap=300,
        length_function=len
    )

    parents = parent_splitter.split_documents(docs)

    # Child chunking
    child_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", ".", " "],
        chunk_size=700,
        chunk_overlap=100,
        length_function=len
    )

    children = []

    for parent_id, parent in enumerate(parents):

        child_chunks = child_splitter.split_documents([parent])

        for child in child_chunks:
            child.metadata["parent_id"] = parent_id
            children.append(child)

    return docs, parents, children
