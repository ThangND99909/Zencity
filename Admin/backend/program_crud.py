# backend/program_crud.py
import json
import threading
from pathlib import Path
from typing import List, Optional
from log_config import make_print

print = make_print(__name__)

# Path to programs.json
DATA_DIR = Path(__file__).parent / "data"
PROGRAMS_FILE = DATA_DIR / "programs.json"

# Đảm bảo thư mục data tồn tại
DATA_DIR.mkdir(exist_ok=True)

# FIX M7: serialize read-modify-write để nhiều request không ghi đè/hỏng file
_programs_lock = threading.Lock()

# Mô hình dữ liệu
class Program:
    def __init__(self, id: str, name: str):
        self.id = id
        self.name = name
    
    def dict(self):
        return {
            "id": self.id,
            "name": self.name
        }


def load_programs() -> List[dict]:
    """Tải danh sách chương trình từ JSON"""
    try:
        if PROGRAMS_FILE.exists():
            with open(PROGRAMS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"❌ Error loading programs: {e}")
        return []


def save_programs(programs: List[dict]) -> bool:
    """Lưu danh sách chương trình vào JSON (ghi atomic)"""
    try:
        # FIX M7: ghi ra temp rồi replace để không hỏng file khi ghi dở
        tmp = PROGRAMS_FILE.with_name(PROGRAMS_FILE.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(programs, f, ensure_ascii=False, indent=2)
        tmp.replace(PROGRAMS_FILE)
        return True
    except Exception as e:
        print(f"❌ Error saving programs: {e}")
        return False


def get_all_programs() -> List[dict]:
    """Lấy tất cả chương trình"""
    return load_programs()


def create_program(name: str) -> Optional[dict]:
    """Tạo chương trình mới"""
    with _programs_lock:
        programs = load_programs()

        # Kiểm tra xem tên đã tồn tại chưa (lowercase comparison)
        name_lower = name.lower()
        if any(p["name"].lower() == name_lower for p in programs):
            return None  # Trùng tên

        # Tạo ID từ tên (lowercase, replace spaces với _)
        new_id = name.lower().replace(" ", "_").strip()

        # Đảm bảo ID duy nhất
        counter = 1
        original_id = new_id
        while any(p["id"] == new_id for p in programs):
            new_id = f"{original_id}_{counter}"
            counter += 1

        new_program = Program(id=new_id, name=name).dict()
        programs.append(new_program)

        if save_programs(programs):
            return new_program
        return None


def update_program(program_id: str, name: str) -> Optional[dict]:
    """Cập nhật chương trình"""
    with _programs_lock:
        programs = load_programs()

        # Tìm chương trình
        program_index = next((i for i, p in enumerate(programs) if p["id"] == program_id), None)
        if program_index is None:
            return None

        # Kiểm tra tên mới không trùng với các chương trình khác
        name_lower = name.lower()
        if any(p["name"].lower() == name_lower and p["id"] != program_id for p in programs):
            return None

        programs[program_index]["name"] = name
        if save_programs(programs):
            return programs[program_index]
        return None


def delete_program(program_id: str) -> bool:
    """Xóa chương trình"""
    with _programs_lock:
        programs = load_programs()

        # Lọc ra chương trình không phải ID cần xóa
        filtered_programs = [p for p in programs if p["id"] != program_id]

        if len(filtered_programs) == len(programs):
            return False  # Không tìm thấy chương trình

        return save_programs(filtered_programs)
