import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, ArrowRight, BookOpen, GraduationCap, Layers } from "lucide-react";
import { SEMESTER_CLASSES } from "./books";
import "../semester.css";

export const metadata: Metadata = {
  title: "E-Books | Semester Book Digital Contents",
};

type Props = {
  searchParams: Promise<{ class?: string; sem?: string }>;
};

export default async function SemesterEbooksPage({ searchParams }: Props) {
  const { class: classId, sem: semId } = await searchParams;
  const cls = SEMESTER_CLASSES.find((c) => c.id === classId);
  const sem = cls?.semesters.find((s) => s.id === semId);

  let heading = "Choose your class";
  let backHref = "/semester";
  if (cls && sem) {
    heading = `${cls.label} · ${sem.label} — Choose a subject`;
    backHref = `/semester/ebooks?class=${cls.id}`;
  } else if (cls) {
    heading = `${cls.label} — Choose a semester`;
    backHref = "/semester/ebooks";
  }

  return (
    <div className="semester-portal">
      <header>
        <div className="nav-container">
          <Link href="/semester" className="brand">
            <div className="brand-icon">
              <Layers style={{ width: 22, height: 22 }} />
            </div>
            <span className="brand-title">Semester Book Digital Contents</span>
          </Link>
        </div>
      </header>

      <section className="hero">
        <div className="hero-badge">
          <BookOpen style={{ width: 14, height: 14 }} />
          E-Book Library
        </div>
        <h1>{heading}</h1>
      </section>

      <main>
        <Link href={backHref} className="sem-back">
          <ArrowLeft style={{ width: 16, height: 16 }} /> Back
        </Link>

        <div className="grid-container sem-grid">
          {!cls &&
            SEMESTER_CLASSES.map((c) => (
              <Link key={c.id} href={`/semester/ebooks?class=${c.id}`} className="action-card">
                <div className="card-icon-wrapper ebook-color">
                  <GraduationCap style={{ width: 28, height: 28 }} />
                </div>
                <h2 className="card-title">{c.label}</h2>
                <span className="card-btn">
                  Open <ArrowRight style={{ width: 16, height: 16 }} />
                </span>
              </Link>
            ))}

          {cls &&
            !sem &&
            cls.semesters.map((s) => (
              <Link
                key={s.id}
                href={`/semester/ebooks?class=${cls.id}&sem=${s.id}`}
                className="action-card"
              >
                <div className="card-icon-wrapper lesson-color">
                  <Layers style={{ width: 28, height: 28 }} />
                </div>
                <h2 className="card-title">{s.label}</h2>
                <span className="card-btn">
                  Open <ArrowRight style={{ width: 16, height: 16 }} />
                </span>
              </Link>
            ))}

          {sem &&
            sem.books.map((b) => (
              <Link key={b.id} href={`/semester/ebooks/${b.id}`} className="action-card sem-book-card">
                <div className="sem-book-cover">
                  <img src={`/semester/ebooks/${b.id}/shot.png`} alt={b.subject} />
                </div>
                <h2 className="card-title">{b.subject}</h2>
                <span className="card-btn">
                  Open Book <ArrowRight style={{ width: 16, height: 16 }} />
                </span>
              </Link>
            ))}
        </div>
      </main>

      <footer>
        &copy; 2026 Semester Book Digital Contents. Designed for NEP & NCF Aligned Classrooms.
      </footer>
    </div>
  );
}
