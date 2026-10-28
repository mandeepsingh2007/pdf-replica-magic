"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

type ClassId = "6" | "7";
type ChapterId = "1" | "2";

type Worksheet = {
  id: string;
  label: string;
  src: string;
};

const CHAPTER_TITLES: Record<ClassId, Record<ChapterId, string>> = {
  "6": {
    "1": "Chapter 1 — Locating Places on the Earth",
    "2": "Chapter 2 — Oceans and Continents",
  },
  "7": {
    "1": "Chapter 1",
    "2": "Chapter 2",
  },
};

const WORKSHEETS: Record<ClassId, Record<ChapterId, Worksheet[]>> = {
  "6": {
    "1": [
      {
        id: "w1",
        label: "Worksheet 1",
        src: "/future-books/worksheets/class-6/chapter-1/worksheet-1.pdf",
      },
      {
        id: "w2",
        label: "Worksheet 2",
        src: "/future-books/worksheets/class-6/chapter-1/worksheet-2.pdf",
      },
      {
        id: "w3",
        label: "Worksheet 3",
        src: "/future-books/worksheets/class-6/chapter-1/worksheet-3.pdf",
      },
    ],
    "2": [
      {
        id: "w1",
        label: "Worksheet 1",
        src: "/future-books/worksheets/class-6/chapter-2/worksheet-1.pdf",
      },
      {
        id: "w2",
        label: "Worksheet 2",
        src: "/future-books/worksheets/class-6/chapter-2/worksheet-2.pdf",
      },
      {
        id: "w3",
        label: "Worksheet 3",
        src: "/future-books/worksheets/class-6/chapter-2/worksheet-3.pdf",
      },
    ],
  },
  "7": {
    "1": [],
    "2": [],
  },
};

export default function FutureBooksWorksheets() {
  const [classId, setClassId] = useState<ClassId>("6");
  const [chapterId, setChapterId] = useState<ChapterId | null>(null);
  const [worksheetId, setWorksheetId] = useState<string | null>(null);

  const worksheets = useMemo(() => {
    if (!chapterId) return [];
    return WORKSHEETS[classId][chapterId];
  }, [classId, chapterId]);

  const activeWorksheet = useMemo(
    () => worksheets.find((item) => item.id === worksheetId) ?? null,
    [worksheets, worksheetId]
  );

  const pickClass = (id: ClassId) => {
    setClassId(id);
    setChapterId(null);
    setWorksheetId(null);
  };

  const pickChapter = (id: ChapterId) => {
    setChapterId(id);
    const first = WORKSHEETS[classId][id][0];
    setWorksheetId(first?.id ?? null);
  };

  return (
    <div className="fb-section-panel">
      <Link href="/future-books" className="fb-back">
        ← Back to Dashboard
      </Link>
      <div className="fb-panel-top">
        <h2>Worksheets</h2>
      </div>
      <p>Choose a class, then a chapter, then open a worksheet.</p>

      <div className="fb-ebook-tabs" role="tablist" aria-label="Choose class">
        {(
          [
            { id: "6", label: "Class 6" },
            { id: "7", label: "Class 7" },
          ] as const
        ).map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={classId === item.id}
            className={`fb-ebook-tab ${classId === item.id ? "is-on" : ""}`}
            onClick={() => pickClass(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="fb-choice-grid" style={{ marginTop: 18 }}>
        {(
          [
            { id: "1", label: "Chapter 1" },
            { id: "2", label: "Chapter 2" },
          ] as const
        ).map((item) => (
          <button
            key={item.id}
            type="button"
            className={`fb-choice ${chapterId === item.id ? "is-on" : ""}`}
            onClick={() => pickChapter(item.id)}
          >
            {item.label}
            <small>{CHAPTER_TITLES[classId][item.id]}</small>
          </button>
        ))}
      </div>

      {chapterId && worksheets.length === 0 && (
        <p className="fb-error" style={{ marginTop: 18 }}>
          Class {classId} Chapter {chapterId} worksheets are not uploaded yet.
        </p>
      )}

      {chapterId && worksheets.length > 0 && (
        <>
          <div className="fb-ebook-tabs" style={{ marginTop: 18 }} aria-label="Choose worksheet">
            {worksheets.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`fb-ebook-tab ${worksheetId === item.id ? "is-on" : ""}`}
                onClick={() => setWorksheetId(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>

          {activeWorksheet && (
            <>
              <div className="fb-ebook-toolbar">
                <strong>
                  Class {classId} · Chapter {chapterId} · {activeWorksheet.label}
                </strong>
                <a
                  className="fb-btn fb-btn-outline"
                  href={activeWorksheet.src}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open in new tab
                </a>
              </div>
              <iframe
                className="fb-ebook-frame"
                title={activeWorksheet.label}
                src={`${activeWorksheet.src}#view=FitH`}
              />
            </>
          )}
        </>
      )}
    </div>
  );
}
