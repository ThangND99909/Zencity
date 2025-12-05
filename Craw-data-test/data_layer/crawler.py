import requests
from bs4 import BeautifulSoup
import json
import re
import os
import logging
from urllib.parse import urljoin, urlparse
from typing import List, Set
import time

from langchain_community.document_loaders import WebBaseLoader
from langchain.schema import Document

# Bổ sung Selenium để giả lập trình duyệt thật (chống chặn bot)
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Tenacity để retry tự động khi tải HTML fail
from tenacity import retry, stop_after_attempt, wait_exponential

# Headers giả lập trình duyệt Chrome (giúp tránh bị chặn 403 Forbidden)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
}

# =============================================================
# Cấu hình logging
# =============================================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# =============================================================
# HÀM TẢI HTML VỚI CƠ CHẾ THỬ LẠI (retry)
# =============================================================
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
def fetch_html(url: str) -> str:
    """Tải HTML từ URL, có retry nếu lỗi mạng hoặc 403"""
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.text

# =============================================================
# HÀM LÀM SẠCH HTML
# =============================================================
def clean_html_text(html: str) -> str:
    """Loại bỏ script, style, footer, header, nav,... và chuẩn hóa text"""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r'\s+', ' ', text)

    # Chuẩn hóa ký tự HTML đặc biệt
    html_entities = {
        '&nbsp;': ' ', '&amp;': '&', '&quot;': '"',
        '&apos;': "'", '&lt;': '<', '&gt;': '>',
        '\u2013': '-', '\u2014': '-', '\u2022': '•',
    }
    for k, v in html_entities.items():
        text = text.replace(k, v)
    return text

# =============================================================
# HÀM CRAWL BẰNG REQUESTS + BEAUTIFULSOUP
# =============================================================
def crawl_url(url: str) -> List[Document]:
    """Tải nội dung trang web bằng requests + BeautifulSoup"""
    try:
        html = fetch_html(url)
        text = clean_html_text(html)
        return [Document(page_content=text, metadata={"url": url})]
    except Exception as e:
        logging.warning(f"Crawl requests+BS4 thất bại {url}: {e}")
        return []

# =============================================================
# LỚP CRAWL BẰNG SELENIUM
# =============================================================
class SeleniumBrowser:
    """Giữ Selenium driver mở để crawl nhiều URL liên tiếp"""
    def __init__(self):
        try:
            options = Options()
            options.add_argument("--headless=new")
            options.add_argument(f"user-agent={HEADERS['User-Agent']}")
            options.add_argument("--disable-blink-features=AutomationControlled")
            self.driver = webdriver.Chrome(options=options)
        except Exception as e:
            logging.error(f"Không thể khởi tạo ChromeDriver: {e}")
            self.driver = None

    def crawl(self, url: str) -> List[Document]:
        if not self.driver:
            return []
        """Tải dữ liệu bằng Selenium (giả lập browser thật)"""
        try:
            self.driver.get(url)
            html = self.driver.page_source
            text = clean_html_text(html)
            return [Document(page_content=text, metadata={"url": url})]
        except Exception as e:
            logging.warning(f"Selenium crawl thất bại {url}: {e}")
            return []

    def close(self):
        """Đóng trình duyệt Selenium"""
        self.driver.quit()

# =============================================================
# HÀM CRAWL AN TOÀN (THỬ NHIỀU CÁCH)
# =============================================================
def safe_load_url(url: str):
    """
    Tải dữ liệu an toàn:
    - Thử WebBaseLoader của LangChain trước
    - Nếu fail, dùng requests + BeautifulSoup
    - Nếu vẫn fail, fallback sang Selenium
    """
    try:
        loader = WebBaseLoader(url)
        docs = loader.load()
        logging.info(f"WebBaseLoader loaded {len(docs)} docs from {url}")
        return docs
    except Exception as e:
        logging.warning(f"WebBaseLoader failed for {url}: {e} → thử requests+BS4")
        docs = crawl_url(url)
        if docs:
            return docs
        logging.warning(f"requests+BS4 cũng fail → thử Selenium")
        browser = SeleniumBrowser()
        docs = browser.crawl(url)
        browser.close()
        return docs

# =============================================================
# LỚP CHÍNH: ZenCrawler — Thu thập dữ liệu ZenCity
# =============================================================
class ZenCrawler:
    """Crawler chuyên dụng cho ZenCity (giáo dục)"""
    def __init__(self):
        # Các nguồn chính của ZenCity
        self.sources = {
            "zencity_home": "https://www.zencityfoundation.org/",  # Trang chính giới thiệu tổ chức :contentReference[oaicite:1]{index=1}
            "zencity_programs": "https://www.zencityfoundation.org/our-programs",  # Trang các chương trình đào tạo :contentReference[oaicite:2]{index=2}
            "zencity_learn_vietnamese": "https://www.zencityfoundation.org/vi/vietnamese",  # Chương trình học tiếng Việt :contentReference[oaicite:3]{index=3}
            "zencity_learn_english": "https://www.zencityfoundation.org/vi/learn-english",  # Chương trình học tiếng Anh :contentReference[oaicite:4]{index=4}
            "zencity_teacher_training": "https://www.zencityfoundation.org/online-teacher-training",  # Khóa đào tạo giáo viên online :contentReference[oaicite:5]{index=5}
            "zencity_accent_training": "https://www.zencityfoundation.org/accent-training",  # Khóa luyện phát âm tiếng Anh (Accent training) :contentReference[oaicite:6]{index=6}
            "zencity_certificates": "https://www.zencityfoundation.org/certificate",  # Mục chứng chỉ & chương trình liên quan :contentReference[oaicite:7]{index=7}
            "zencity_events": "https://www.zencityfoundation.org/event-list",  # Trang sự kiện của tổ chức :contentReference[oaicite:8]{index=8}
            "zencity_blog_post_english_for_workers": "https://www.zencityfoundation.org/post/kham-pha-khoa-hoc-tieng-anh-danh-cho-nguoi-di-lam-tai-zen-city-foundation",  # Ví dụ bài viết blog ‎:contentReference[oaicite:9]{index=9}
        }
        self.crawled_urls: Set[str] = set()

    # =============================================================
    # LẤY TẤT CẢ LINK CON TRONG 1 TRANG CHÍNH
    # =============================================================
    def get_all_links(self, base_url: str, limit: int = 20) -> List[str]:
        """Lấy toàn bộ link con trong cùng domain (giới hạn limit)"""
        try:
            html = fetch_html(base_url)
        except Exception as e:
            logging.error(f"Error fetching {base_url}: {e}")
            return []

        soup = BeautifulSoup(html, "html.parser")
        base_domain = urlparse(base_url).netloc
        links: Set[str] = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            full_url = urljoin(base_url, href)
            # Chỉ lấy link trong cùng domain
            if urlparse(full_url).netloc == base_domain:
                links.add(full_url)

        links = list(links)[:limit]
        logging.info(f"🔗 Found {len(links)} links in {base_url}")
        return links

    # =============================================================
    # CRAWL TOÀN BỘ DOMAIN
    # =============================================================
    def crawl_domain(self, source_name: str, base_url: str, limit: int = 20) -> List[Document]:
        """
        Crawl toàn bộ link con trong 1 domain:
        - Thêm metadata: source, url, length
        - Tránh crawl trùng lặp
        """
        docs = []
        urls = self.get_all_links(base_url, limit=limit)
        if base_url not in urls:
            urls.insert(0, base_url)

        for url in urls:
            if url in self.crawled_urls:
                continue
            try:
                loaded_docs = safe_load_url(url)  # Dùng safe_load_url thay vì crawl trực tiếp
                for doc in loaded_docs:
                    doc.metadata["source"] = source_name
                    doc.metadata["url"] = url
                    doc.metadata["length"] = len(doc.page_content.split())
                docs.extend(loaded_docs)
                self.crawled_urls.add(url)
                logging.info(f"Crawled {len(loaded_docs)} docs from {url}")
            except Exception as e:
                logging.warning(f"Skipped {url}: {e}")
        return docs

    # =============================================================
    # LƯU TÀI LIỆU RA FILE JSONL
    # =============================================================
    def save_documents_to_jsonl(self, docs: List[Document], filename: str):
        """Lưu danh sách documents ra file JSONL"""
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w", encoding="utf-8") as f:
            for doc in docs:
                f.write(json.dumps({
                    "content": doc.page_content,
                    "metadata": doc.metadata
                }, ensure_ascii=False) + "\n")
        logging.info(f"Saved {len(docs)} documents to {filename}")
