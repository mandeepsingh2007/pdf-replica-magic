import os
import uuid
import shutil
from fastapi import UploadFile

def ensure_dir_exists(dir_path: str) -> None:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

def save_upload_file(file: UploadFile, upload_dir: str) -> tuple[str, str]:
    ensure_dir_exists(upload_dir)
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(upload_dir, unique_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return unique_filename, file_path

def get_file_size(file_path: str) -> int:
    return os.path.getsize(file_path)

def delete_file(file_path: str) -> bool:
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        return True
    except Exception:
        return False
