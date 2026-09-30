from langchain_community.document_loaders import (
    PyMuPDFLoader,
    Docx2txtLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter 


def ingest_spec(file_path:str):
    """
    Load the file into Langchain docs ."""

    if file_path.endswith(".pdf"):
        loader = PyMuPDFLoader(file_path)
    elif file_path.endswith(".docx"):
        loader = Docx2txtLoader(file_path)
    else:
        raise ValueError("Unsupported file type")
    
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(
        separators= ["\n\n" , "\n" , "." , " "] ,
        chunk_size=8000 ,
        chunk_overlap=500 , 
        length_function=len 
        )

    chunks = splitter.split_documents(docs)
    return chunks 
     
    


        