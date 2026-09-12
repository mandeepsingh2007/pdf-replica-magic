"""
Re-process all 6 scanned PDFs using Gemini Vision API for OCR.
Extracts text from each page image and saves as chunks.
"""
import sys
import os
import time
import json
import sqlite3
import base64

sys.path.insert(0, os.path.dirname(__file__))

import fitz  # PyMuPDF
import google.generativeai as genai

# Load API key from .env
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("ERROR: GEMINI_API_KEY not found in .env")
    sys.exit(1)

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

DB_PATH = os.path.join(os.path.dirname(__file__), "test_generator.db")

OCR_PROMPT = """You are an expert OCR system. Extract ALL text content from this scanned textbook page image.

Rules:
1. Extract every word, sentence, paragraph, heading, subheading, and caption visible on the page.
2. Preserve the logical reading order (top to bottom, left to right).
3. Use markdown formatting for headings (# for chapter titles, ## for section headings, etc.).
4. If there are tables, reproduce them in a readable format.
5. If there are math equations, write them in plain text notation.
6. If there are diagrams/figures, write [FIGURE: brief description] as a placeholder.
7. Skip page numbers, watermarks, and publisher logos.
8. Output ONLY the extracted text. No commentary.
"""

def ocr_page_with_gemini(page, page_num: int, retries: int = 3) -> str:
    """Convert a PDF page to image and OCR it using Gemini Vision."""
    # Render page to image at 150 DPI (balance between quality and speed)
    pix = page.get_pixmap(dpi=150)
    img_bytes = pix.tobytes("png")
    
    for attempt in range(retries):
        try:
            response = model.generate_content([
                OCR_PROMPT,
                {"mime_type": "image/png", "data": img_bytes}
            ])
            text = response.text.strip()
            if text:
                return text
        except Exception as e:
            print(f"    Attempt {attempt+1} failed for page {page_num}: {e}")
            if "429" in str(e) or "quota" in str(e).lower() or "rate" in str(e).lower():
                wait_time = 15 * (attempt + 1)
                print(f"    Rate limited. Waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                time.sleep(3)
    
    return ""


def chunk_text(full_text: str, max_chars: int = 1500) -> list:
    """Split text into chunks of roughly max_chars, splitting at paragraph boundaries."""
    paragraphs = full_text.split("\n\n")
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current_chunk) + len(para) > max_chars and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = para + "\n\n"
        else:
            current_chunk += para + "\n\n"
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Clear existing chunks
    cursor.execute("DELETE FROM chunks")
    conn.commit()
    
    # Get all documents
    cursor.execute("SELECT id, file_path, original_filename, subject_id FROM documents")
    documents = cursor.fetchall()
    
    total_chunks_inserted = 0
    
    for doc_id, file_path, filename, subject_id in documents:
        print(f"\n{'='*60}")
        print(f"Processing: {filename} (doc_id={doc_id})")
        
        if not os.path.exists(file_path):
            print(f"  ERROR: File not found at {file_path}")
            continue
        
        doc = fitz.open(file_path)
        total_pages = len(doc)
        print(f"  Total pages: {total_pages}")
        
        all_page_texts = []
        
        for page_num in range(total_pages):
            page = doc.load_page(page_num)
            
            # First try native text extraction
            native_text = page.get_text().strip()
            
            if native_text and len(native_text) > 50:
                # Native text available (not a scanned page)
                print(f"  Page {page_num+1}/{total_pages}: Native text ({len(native_text)} chars)")
                all_page_texts.append({
                    "page": page_num + 1,
                    "text": native_text
                })
            else:
                # Scanned page - use Gemini OCR
                print(f"  Page {page_num+1}/{total_pages}: OCR via Gemini...", end=" ", flush=True)
                ocr_text = ocr_page_with_gemini(page, page_num + 1)
                if ocr_text:
                    print(f"({len(ocr_text)} chars)")
                    all_page_texts.append({
                        "page": page_num + 1,
                        "text": ocr_text
                    })
                else:
                    print("(no text extracted)")
                
                # Rate limit: wait between pages to avoid 429
                time.sleep(2)
        
        doc.close()
        
        # Combine all page texts and chunk them
        for page_data in all_page_texts:
            page_text = page_data["text"]
            page_num = page_data["page"]
            
            # Chunk each page's text
            page_chunks = chunk_text(page_text)
            
            for idx, chunk_content in enumerate(page_chunks):
                if len(chunk_content.strip()) < 20:
                    continue  # Skip tiny chunks
                    
                cursor.execute("""
                    INSERT INTO chunks (document_id, content, chunk_index, chunk_type, page_number, section_path, embedding, token_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    doc_id,
                    chunk_content,
                    total_chunks_inserted,
                    "text",
                    page_num,
                    "General",
                    "[0.1, 0.2, 0.3]",  # Placeholder embedding
                    len(chunk_content.split())
                ))
                total_chunks_inserted += 1
        
        conn.commit()
        
        # Count chunks for this document
        cursor.execute("SELECT COUNT(*) FROM chunks WHERE document_id = ?", (doc_id,))
        doc_chunks = cursor.fetchone()[0]
        print(f"  ✓ Saved {doc_chunks} chunks for {filename}")
    
    # Final summary
    print(f"\n{'='*60}")
    print("FINAL SUMMARY:")
    cursor.execute("SELECT d.original_filename, COUNT(c.id) FROM documents d LEFT JOIN chunks c ON d.id = c.document_id GROUP BY d.id")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} chunks")
    print(f"\nTOTAL CHUNKS: {total_chunks_inserted}")
    
    conn.close()


if __name__ == "__main__":
    main()
