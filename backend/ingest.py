import os
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import Docx2txtLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS


def main() -> None:
    backend_dir = Path(__file__).resolve().parent
    project_root = backend_dir.parent
    docx_path = Path(
        os.getenv("DOCX_PATH", str(project_root / "Mentoring Startups GuideF.docx"))
    )
    index_dir = Path(os.getenv("FAISS_INDEX_DIR", str(backend_dir / "faiss_index")))

    if not docx_path.exists():
        raise FileNotFoundError(
            f"DOCX file not found at '{docx_path}'. "
            "Place 'Mentoring Startups GuideF.docx' in the project root or set DOCX_PATH."
        )

    print(f"Loading document from: {docx_path}")
    loader = Docx2txtLoader(str(docx_path))
    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    print(f"Created {len(chunks)} chunks.")

    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectorstore = FAISS.from_documents(chunks, embeddings)

    index_dir.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(index_dir))
    print(f"FAISS index saved to: {index_dir}")


if __name__ == "__main__":
    main()
