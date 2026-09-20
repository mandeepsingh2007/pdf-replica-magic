"""Read-only local verification; no LLM calls or database writes."""
import asyncio
import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.services.chapter_service import extract_chapters, filter_chunks_by_chapters
from app.services.question_generator import generate_picture_match
from app.services.verified_hindi_source import verified_page_texts


async def verify():
    db = sqlite3.connect(f'file:{(BACKEND / "test_generator.db").as_posix()}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    doc = db.execute("SELECT d.* FROM documents d JOIN subjects s ON s.id=d.subject_id WHERE lower(s.name)='hindi-1'").fetchone()
    chunks = [SimpleNamespace(**dict(row)) for row in db.execute('SELECT * FROM chunks WHERE document_id=? ORDER BY chunk_index', (doc['id'],))]
    assert len(chunks) == 82
    assert all(json.loads(c.metadata_json)['page_isolated'] for c in chunks)
    chapters = extract_chapters(chunks, subject_name='Hindi-1')
    assert len(chapters) == 14
    for chapter in chapters:
        selected = filter_chunks_by_chapters(chunks, [chapter.id], subject_name='Hindi-1')
        assert {c.page_number for c in selected} == set(range(chapter.start_page, chapter.end_page + 1))
    selection = filter_chunks_by_chapters(chunks, ['ch-h1-4', 'ch-h1-5', 'ch-h1-6'], subject_name='Hindi-1')
    assert [c.page_number for c in selection] == [4, 5, 6, 7]
    for c in selection:
        assert c.content == verified_page_texts(doc['file_path'])[c.page_number]
    images = [dict(row) for row in db.execute('SELECT id, image_path, page_number, caption, vlm_description AS description, bbox_width, bbox_height FROM extracted_images WHERE document_id=? AND image_path LIKE ?', (doc['id'], '%verified_hindi_1%'))]
    assert len(images) == 14
    # Fail if this local check accidentally tries to call an external model/OCR.
    with patch('app.services.question_generator.picture_match_label', new_callable=AsyncMock, side_effect=AssertionError('Unexpected OCR')), patch('app.services.question_generator.generate_structured_output', new_callable=AsyncMock, side_effect=AssertionError('Unexpected LLM')):
        result = await generate_picture_match('Verified national symbols', 1, 'Hindi', [i for i in images if i['page_number'] == 7], 'PDF page 7')
    assert len(result) == 1
    pictures = result[0]['data']['pictures']
    assert len({p['image_id'] for p in pictures}) == 5
    assert all(next(i for i in images if i['id'] == p['image_id'])['page_number'] == 7 for p in pictures)
    story_selection = filter_chunks_by_chapters(chunks, ['ch-h1-12', 'ch-h1-13', 'ch-h1-14'], subject_name='Hindi-1')
    story_pages = {c.page_number for c in story_selection}
    assert story_pages == {72,73,74,75,76,77,79,80,81}
    # Include the actual mixed pool (old unlabeled images and repaired figures).
    story_images = [dict(row) for row in db.execute('SELECT id, image_path, page_number, caption, vlm_description AS description, bbox_width, bbox_height FROM extracted_images WHERE document_id=?', (doc['id'],)) if row['page_number'] in story_pages]
    # Expansion can write new panels, so the read-only verifier instead checks
    # whether any verified single figure would be split by its detector.
    from app.services.image_quality import is_stacked_composite
    assert not any(is_stacked_composite(i['image_path']) for i in images if i['page_number'] == 74)
    with patch('app.services.question_generator.picture_match_label', new_callable=AsyncMock, side_effect=AssertionError('Unexpected OCR')), patch('app.services.question_generator.generate_structured_output', new_callable=AsyncMock, side_effect=AssertionError('Unexpected LLM')):
        story_result = await generate_picture_match('Selected story chapters', 1, 'Hindi', story_images, 'PDF pages 72–77, 79–81')
    story_pictures = story_result[0]['data']['pictures']
    assert len({p['image_id'] for p in story_pictures}) == 5
    assert all(next(i for i in images if i['id'] == p['image_id'])['page_number'] == 74 for p in story_pictures)
    print('PASS: story chapters 12–14 produce all five real matching images from PDF page 74, with no external calls.')
    print('PASS: 82 page-isolated chunks; all 14 chapter ranges; 14 verified figures across pages 7 and 74; both picture-match selections pass without OCR or LLM calls.')
    db.close()


if __name__ == '__main__':
    asyncio.run(verify())
