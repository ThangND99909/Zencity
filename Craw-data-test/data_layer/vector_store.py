from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.schema import BaseRetriever, Document
from typing import List, Dict, Any
import json
import numpy as np
import os
from preprocessor import ZenPreprocessor

class ZenVectorStoreManager:
    """
    Vector Store Manager tối ưu cho ZenCity:
    - Tự động dùng ZenPreprocessor
    - Embedding đa ngôn ngữ
    - Thư mục và file lưu trữ riêng
    """
    def __init__(self, embedding_model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        # Khởi tạo embedding
        self.embedding_model = HuggingFaceEmbeddings(
            model_name=embedding_model,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': False}
        )
        self.vector_store = None
        self.persist_directory = "./chroma_db_zen"
        self.json_path = "data/zen_full_documents.json"
        self.npz_path = "data/zen_embeddings.npz"
        self.preprocessor = ZenPreprocessor()

    # Kiểm tra vector store đã được khởi tạo chưa
    def is_initialized(self) -> bool:
        return self.vector_store is not None

    # ================== TẠO / LOAD VECTOR STORE ==================
    def create_vector_store(self, documents: List[Document]):
        """Tạo mới vector store và lưu JSON + embeddings"""
        self.vector_store = Chroma.from_documents(
            documents=documents,
            embedding=self.embedding_model,
            persist_directory=self.persist_directory
        )
        self.vector_store.persist()

        # Lưu JSON
        os.makedirs(os.path.dirname(self.json_path), exist_ok=True)
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump([{"content": d.page_content, "metadata": d.metadata} for d in documents],
                      f, ensure_ascii=False, indent=2)

        # Lưu embeddings
        texts = [d.page_content for d in documents]
        embeddings = self.embedding_model.embed_documents(texts)
        np.savez_compressed(self.npz_path, embeddings=embeddings, metadata=[d.metadata for d in documents])
        return self.vector_store

    def load_vector_store(self):
        """Load vector store từ folder"""
        if os.path.exists(self.persist_directory):
            self.vector_store = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embedding_model
            )
            print(f"Vector store loaded từ {self.persist_directory}")
        else:
            print(f"Vector store chưa tồn tại tại {self.persist_directory}")
        return self.vector_store

    def load_or_create_vector_store(self, force_create=False):
        """Load nếu tồn tại, tạo mới nếu không hoặc force_create=True"""
        if os.path.exists(self.persist_directory) and not force_create:
            try:
                return self.load_vector_store()
            except Exception as e:
                print(f"Không load được, sẽ tạo mới: {e}")
        # Tạo mới vector store rỗng
        self.vector_store = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embedding_model
        )
        print(f"Tạo vector store mới tại {self.persist_directory}")
        return self.vector_store

    # ================== TRUY VẤN ==================
    def search_similar_documents(self, query: str, k: int = 5):
        if self.vector_store is None:
            raise ValueError("Vector store chưa khởi tạo")
        return self.vector_store.similarity_search(query, k=k)

    def as_retriever(self, search_type: str = "similarity", k: int = 5, **kwargs) -> BaseRetriever:
        if self.vector_store is None:
            raise ValueError("Vector store chưa khởi tạo")
        return self.vector_store.as_retriever(search_type=search_type, search_kwargs={"k": k, **kwargs})

    # ================== QUẢN LÝ ==================
    def add_documents(self, documents: List[Document], persist: bool = True):
        if not self.is_initialized():
            self.load_or_create_vector_store()
        ids = self.vector_store.add_documents(documents)
        if persist:
            self.vector_store.persist()
        return ids

    def delete_documents(self, ids: List[str], persist: bool = True):
        if self.vector_store is None:
            raise ValueError("Vector store chưa khởi tạo")
        self.vector_store.delete(ids)
        if persist:
            self.vector_store.persist()

    def clear_vector_store(self):
        if self.vector_store is None:
            raise ValueError("Vector store chưa khởi tạo")
        collection = self.vector_store._collection
        if collection:
            collection.delete(where={})
            self.vector_store.persist()

    def health_check(self) -> Dict[str, Any]:
        return {
            "initialized": self.vector_store is not None,
            "document_count": self.vector_store._collection.count() if self.vector_store else 0,
            "persist_directory": self.persist_directory,
            "status": "healthy" if self.vector_store else "not_initialized"
        }

    # ================== LOAD DOCUMENTS ==================
    def load_documents_from_jsonl(self, filename: str) -> List[Document]:
        documents = []
        with open(filename, "r", encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line)
                documents.append(Document(page_content=obj["content"], metadata=obj["metadata"]))
        return documents

    def index_from_jsonl(self, jsonl_file: str):
        docs = self.load_documents_from_jsonl(jsonl_file)
        return self.create_vector_store(docs)

    # ================== IMPORT FILES ==================
    def import_file(self, file_path: str, chunk_size: int = 1000, chunk_overlap: int = 200):
        text = ""
        if file_path.lower().endswith(".pdf"):
            text = self.preprocessor.read_pdf(file_path)
        elif file_path.lower().endswith(".txt"):
            text = self.preprocessor.read_txt(file_path)
        elif file_path.lower().endswith(".docx"):
            text = self.preprocessor.read_docx(file_path)
        else:
            raise ValueError(f"Không hỗ trợ định dạng: {file_path}")

        if not text.strip():
            print(f"File rỗng hoặc không đọc được: {file_path}")
            return

        doc = Document(page_content=text, metadata={"source": file_path})
        chunks = self.preprocessor.split_documents([doc], chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        if not self.is_initialized():
            self.load_or_create_vector_store()

        ids = self.vector_store.add_documents(chunks)
        self.vector_store.persist()
        print(f"Đã import {len(chunks)} chunks từ {file_path}")
        return ids


# ================== GLOBAL INSTANCE ==================
zen_vector_store_manager = ZenVectorStoreManager()
vector_store = zen_vector_store_manager
