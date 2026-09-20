"""Repair this verified edition without altering saved tests or other books.

Run from backend: venv/Scripts/python.exe scripts/repair_hindi_page_chunks.py
Creates a consistent SQLite backup before committing the scoped repair.
"""
import json
import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pymupdf

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.services.chunking import generate_embeddings, layout_aware_chunking
from app.services.verified_hindi_source import verified_page_texts


def repair(*, images_only=False):
    source = BACKEND.parent / 'test pdf/original books/hindi/Hindi Pathmala-1 (Proof 2)_optimize.pdf'
    corrections = verified_page_texts(str(source))
    if not corrections:
        raise RuntimeError('Source PDF does not match the visually verified edition.')
    db = sqlite3.connect(BACKEND / 'test_generator.db', timeout=60)
    row = db.execute("SELECT d.id FROM documents d JOIN subjects s ON s.id=d.subject_id WHERE lower(s.name)='hindi-1' AND d.file_path=?", (str(source),)).fetchone()
    if not row:
        raise RuntimeError('Matching Hindi-1 document not found.')
    document_id = row[0]
    backup_dir = BACKEND / 'backups'
    backup_dir.mkdir(exist_ok=True)
    backup_path = backup_dir / f'chapter-repair-{datetime.now():%Y%m%d-%H%M%S-%f}.db'
    with sqlite3.connect(backup_path) as backup:
        db.backup(backup)

    # Render actual page appearances: raw embedded image bytes in this PDF
    # contain masks/repeated textures and cannot be used as faithful figures.
    crops_by_page = {7: [
        ('तिरंगा', (65, 175, 205, 280)),
        ('आम', (265, 170, 367, 278)),
        ('मोर', (455, 168, 601, 278)),
        ('बाघ', (65, 350, 217, 493)),
        ('कमल', (252, 354, 403, 491)),
        ('महात्मा गाँधी', (452, 349, 592, 490)),
        ('रुपया', (80, 565, 188, 668)),
        ('हॉकी', (277, 563, 383, 665)),
        ('अशोक स्तंभ', (496, 558, 559, 673)),
    ], 74: [
        ('चिड़िया', (68, 334, 166, 450)),
        ('पेड़', (63, 540, 167, 642)),
        ('घोंसला', (462, 324, 617, 427)),
        ('आसमान', (451, 489, 631, 619)),
        ('चिड़िया अण्डे', (65, 460, 159, 536)),
    ]}
    image_dir = BACKEND / 'uploads' / 'verified_hindi_1'
    image_dir.mkdir(parents=True, exist_ok=True)
    images = []
    with pymupdf.open(source) as pdf:
        blocks = [{'page': i+1, 'text': corrections.get(i+1, page.get_text().strip())} for i, page in enumerate(pdf)]
        for page_number, crops in crops_by_page.items():
            for i, (label, coords) in enumerate(crops):
                page = pdf[page_number - 1]
                sx, sy = page.rect.width / 648, page.rect.height / 828
                rect = pymupdf.Rect(coords[0]*sx, coords[1]*sy, coords[2]*sx, coords[3]*sy)
                path = image_dir / f'page{page_number}_verified{i}.png'
                page.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=rect).save(path)
                images.append((str(path), label, rect, page_number))
    chunks = generate_embeddings(layout_aware_chunking(blocks))
    assert {c['page_number'] for c in chunks} == set(range(1, 83))
    with db:
        if not images_only:
            db.execute('DELETE FROM chunks WHERE document_id=?', (document_id,))
            for i, chunk in enumerate(chunks):
                db.execute('INSERT INTO chunks (document_id,content,chunk_index,chunk_type,page_number,section_path,embedding,token_count,metadata_json) VALUES (?,?,?,?,?,?,?,?,?)',
                    (document_id, chunk['content'], i, 'text', chunk['page_number'], 'Page-isolated v2', chunk['embedding'], chunk['token_count'], json.dumps({'page_isolated': True, 'visually_transcribed': chunk['page_number'] in corrections})))
        for path, label, rect, page_number in images:
            existing = db.execute('SELECT id FROM extracted_images WHERE document_id=? AND image_path=?', (document_id, path)).fetchone()
            if existing:
                db.execute('UPDATE extracted_images SET caption=?,vlm_description=? WHERE id=?', (label, label, existing[0]))
            else:
                db.execute('INSERT INTO extracted_images (document_id,image_path,page_number,caption,vlm_description,bbox_x,bbox_y,bbox_width,bbox_height) VALUES (?,?,?,?,?,?,?,?,?)',
                    (document_id, path, page_number, label, label, rect.x0, rect.y0, rect.width, rect.height))
    db.close()
    print(f'Repaired document {document_id}: {"preserved existing chunks" if images_only else str(len(chunks)) + " page-isolated chunks"}, {len(images)} verified figures. Backup: {backup_path}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--images-only', action='store_true', help='Repair verified figures without replacing text chunks')
    repair(images_only=parser.parse_args().images_only)
