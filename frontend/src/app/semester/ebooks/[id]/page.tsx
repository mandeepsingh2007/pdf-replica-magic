import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { SEMESTER_CLASSES, findSemesterBook } from "../books";
import "../../semester.css";

type Props = {
  params: Promise<{ id: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const found = findSemesterBook(id);
  return {
    title: found
      ? `${found.book.subject} | Semester Book Digital Contents`
      : "E-Book | Semester Book Digital Contents",
  };
}

export function generateStaticParams() {
  return SEMESTER_CLASSES.flatMap((c) =>
    c.semesters.flatMap((s) => s.books.map((b) => ({ id: b.id })))
  );
}

export default async function SemesterEbookReaderPage({ params }: Props) {
  const { id } = await params;
  const found = findSemesterBook(id);
  if (!found) notFound();
  const { cls, sem, book } = found;

  return (
    <div className="semester-portal sem-reader">
      <div className="sem-reader-bar">
        <Link href={`/semester/ebooks?class=${cls.id}&sem=${sem.id}`} className="sem-back">
          <ArrowLeft style={{ width: 16, height: 16 }} /> Subjects
        </Link>
        <div className="sem-reader-title">
          <strong>{book.subject}</strong>
          <span>
            {cls.label} · {sem.label}
          </span>
        </div>
        <Link href="/semester" className="sem-back">
          Portal
        </Link>
      </div>
      <iframe
        className="sem-reader-frame"
        title={book.subject}
        src={`/semester/ebooks/${book.id}/${book.entry}`}
        allow="fullscreen"
      />
    </div>
  );
}
