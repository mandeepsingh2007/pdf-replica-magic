import type { Metadata } from "next";
import Link from "next/link";
import { fetchSubjectsOnServer } from "@/lib/server-api";
import FutureBooksGenerator from "./FutureBooksGenerator";
import "../future-books.css";

export const metadata: Metadata = {
  title: "Test Paper Generator | Future Books",
};

export default async function FutureBooksGeneratePage() {
  const { subjects, error } = await fetchSubjectsOnServer("future");

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
          <span className="fb-pill">TEST PAPER GENERATOR</span>
          <Link href="/future-books/login" className="fb-btn fb-btn-outline">
            Log Out
          </Link>
        </div>
      </header>

      <main className="fb-main">
        <div className="fb-dash-intro">
          <div>
            <div className="fb-eyebrow">Future Books</div>
            <h1>Test Paper Generator</h1>
            <p>Create a Social Science paper from the Class 6 or Class 7 textbook.</p>
          </div>
        </div>
        <FutureBooksGenerator initialSubjects={subjects} initialLoadError={error ?? undefined} />
      </main>

      <footer className="fb-foot">© {new Date().getFullYear()} Future Books. Digital teaching and learning resources.</footer>
    </div>
  );
}
