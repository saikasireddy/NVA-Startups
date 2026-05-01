import os
from typing import List, Tuple

import streamlit as st
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import PromptTemplate
from langchain_community.document_loaders import Docx2txtLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.llms import Ollama
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter


st.set_page_config(
    page_title="NVA Mentoring Startups Guide Assistant",
    page_icon="🚀",
    layout="wide",
)

st.title("🚀 NVA Mentoring Startups Guide Assistant")
st.caption("Ask questions about mentoring startups using the local guide and local Llama 3.")


SYSTEM_PROMPT_TEMPLATE = """
You are a practical startup mentoring assistant for the New Venture Accelerator.
Use only the context below from the Mentoring Startups Guide to answer.
If the answer is not contained in the context, clearly say you do not know
based on the provided guide and suggest what section/topic the user should review.

Context:
{context}

Chat History:
{chat_history}

Question:
{question}

Helpful, concise answer:
"""


@st.cache_resource(show_spinner=False)
def build_vectorstore(docx_path: str) -> FAISS:
    """
    Load the DOCX mentoring guide, chunk it, embed chunks locally, and return FAISS index.
    Cached as a Streamlit resource so indexing runs once per app session/environment.
    """
    if not os.path.exists(docx_path):
        raise FileNotFoundError(
            f"Document not found: {docx_path}. Place the DOCX in the app directory."
        )

    loader = Docx2txtLoader(docx_path)
    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)

    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectorstore = FAISS.from_documents(chunks, embeddings)
    return vectorstore


def build_rag_chain(vectorstore: FAISS) -> ConversationalRetrievalChain:
    """
    Construct conversational RAG chain using local Ollama Llama 3 + FAISS retriever.
    """
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    prompt = PromptTemplate(
        input_variables=["context", "chat_history", "question"],
        template=SYSTEM_PROMPT_TEMPLATE,
    )

    # Ensure llama3 is available locally before running:
    # In terminal, run once: ollama run llama3
    llm = Ollama(model="llama3", temperature=0.2)

    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        combine_docs_chain_kwargs={"prompt": prompt},
        return_source_documents=False,
    )
    return chain


def streamlit_history_to_langchain(messages: List[dict]) -> List[Tuple[str, str]]:
    """
    Convert Streamlit-style message history to (human, ai) tuples for LangChain.
    """
    history_pairs: List[Tuple[str, str]] = []
    pending_user = None

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")

        if role == "user":
            pending_user = content
        elif role == "assistant" and pending_user is not None:
            history_pairs.append((pending_user, content))
            pending_user = None

    return history_pairs


def main() -> None:
    docx_file = "Mentoring Startups GuideF.docx"

    with st.spinner("Building mentoring guide index (first run may take a minute)..."):
        try:
            vectorstore = build_vectorstore(docx_file)
        except FileNotFoundError as e:
            st.error(str(e))
            st.stop()
        except Exception as e:
            st.error(
                f"Failed to build the document index. Details: {e}"
            )
            st.stop()

    try:
        rag_chain = build_rag_chain(vectorstore)
    except Exception as e:
        st.error(
            "Could not initialize Ollama Llama 3. Confirm Ollama is running and the model is installed.\n"
            f"Details: {e}"
        )
        st.stop()

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "Hi! Ask me anything about mentoring startups. "
                    "I will answer using the NVA guide context."
                ),
            }
        ]

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_query = st.chat_input("Ask about mentoring startups...")
    if user_query:
        st.session_state.messages.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                history = streamlit_history_to_langchain(st.session_state.messages[:-1])
                try:
                    result = rag_chain.invoke(
                        {"question": user_query, "chat_history": history}
                    )
                    answer = result.get("answer", "I could not generate an answer.")
                except Exception as e:
                    answer = (
                        "I ran into an issue while generating the response. "
                        "Please verify Ollama is running locally (`ollama serve`) and try again.\n\n"
                        f"Error details: {e}"
                    )

                st.markdown(answer)

        st.session_state.messages.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()
