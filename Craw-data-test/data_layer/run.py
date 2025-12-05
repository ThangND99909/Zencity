from crawler import ZenCrawler
from preprocessor import ZenPreprocessor
from vector_store import zen_vector_store_manager  # instance global của Zen

def count_words(docs):
    """Đếm tổng số từ trong danh sách documents"""
    return sum(len(doc.page_content.split()) for doc in docs)

if __name__ == "__main__":
    # =========================
    # 1. Crawl dữ liệu ZenCity
    # =========================
    crawler = ZenCrawler()
    raw_docs = []
    for key, url in crawler.sources.items():
        raw_docs.extend(crawler.crawl_domain(key, url, limit=30))
    print(f"Số lượng tài liệu thu thập ban đầu: {len(raw_docs)}")
    print(f"Tổng số từ (raw): {count_words(raw_docs)}")

    # =====================================
    # 2. Tiền xử lý: clean + chunk ZenDocs
    # =====================================
    preprocessor = ZenPreprocessor()
    processed_docs = preprocessor.clean_and_chunk(raw_docs)
    print(f"Số lượng đoạn văn bản sau khi làm sạch + chunk: {len(processed_docs)}")
    print(f"Tổng số từ (processed): {count_words(processed_docs)}")

    # =====================================
    # 3. Lưu dữ liệu thô đã xử lý ra JSONL
    # =====================================
    jsonl_file = "data/zen_full_documents.jsonl"
    preprocessor.save_to_jsonl(processed_docs, jsonl_file)

    # =================================================
    # 4. Load dữ liệu từ JSONL + index vào VectorStore
    # =================================================
    zen_vector_store_manager.index_from_jsonl(jsonl_file)
    vector_store_instance = zen_vector_store_manager.vector_store  # Giữ reference nếu cần

    print("Pipeline completed: Crawl → Preprocess → JSONL + JSON + NPZ + ChromaDB saved")
