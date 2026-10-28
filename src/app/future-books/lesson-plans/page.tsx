import type { Metadata } from "next";
import Link from "next/link";
import "../future-books.css";
import FutureBooksLessonPlans from "./FutureBooksLessonPlans";

export const metadata: Metadata = {
  title: "Lesson Plans | Future Books",
};

export default function FutureBooksLessonPlansPage() {
  return (
    <div className="future-books">
      <header className="fb-header">
        <Link href="/future-books" className="fb-brand">
          <div className="fb-brand-icon" aria-hidden="true">
            📖
          </div>
          <div>
            <div className="fb-brand-name">Future Books</div>
            <div className="fb-brand-sub">DIGITAL CONTENTS</div>
          </div>
        </Link>
        <div className="fb-header-right">
          <span className="fb-pill">A DIGITAL LEARNING LIBRARY</span>
          <Link href="/future-books/login" prefetch={false} className="fb-btn fb-btn-outline">
            Log Out
          </Link>
        </div>
      </header>

      <main className="fb-main">
        <FutureBooksLessonPlans />
      </main>

      <footer className="fb-foot">
        © {new Date().getFullYear()} Future Books. Digital teaching and learning resources.
      </footer>
    </div>
  );
}
