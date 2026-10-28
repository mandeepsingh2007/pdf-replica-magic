"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

const BOOKS = [
  {
    id: "6",
    label: "Class 6",
    title: "Social Science — Class 6",
    src: "/future-books/ebooks/class-6.pdf",
  },
  {
    id: "7",
    label: "Class 7",
    title: "Social Science — Class 7 (Part-1)",
    src: "/future-books/ebooks/class-7.pdf",
  },
] as const;

export default function FutureBooksEbooks() {
  const [activeId, setActiveId] = useState<(typeof BOOKS)[number]["id"]>("6");
  const book = useMemo(
    () => BOOKS.find((item) => item.id === activeId) ?? BOOKS[0],
    [activeId]
  );

  return (
    <div className="fb-section-panel fb-ebooks">
      <Link href="/future-books" className="fb-back">
        ← Back to Dashboard
      </Link>
      <div className="fb-panel-top">
        <h2>E-Books</h2>
      </div>
      <p>Open the Social Science textbook for Class 6 or Class 7.</p>

      <div className="fb-ebook-tabs" role="tablist" aria-label="Choose class">
        {BOOKS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={activeId === item.id}
            className={`fb-ebook-tab ${activeId === item.id ? "is-on" : ""}`}
            onClick={() => setActiveId(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="fb-ebook-toolbar">
        <strong>{book.title}</strong>
        <a className="fb-btn fb-btn-outline" href={book.src} target="_blank" rel="noreferrer">
          Open in new tab
        </a>
      </div>

      <iframe className="fb-ebook-frame" title={book.title} src={`${book.src}#view=FitH`} />
    </div>
  );
}
