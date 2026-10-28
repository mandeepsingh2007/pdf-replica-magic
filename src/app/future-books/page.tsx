import type { Metadata } from "next";
import Link from "next/link";
import "./future-books.css";

export const metadata: Metadata = {
  title: "Digital Contents | Future Books",
};

const TILES = [
  {
    title: "E-Books",
    desc: "Browse Class 6 and Class 7 Social Science textbooks",
    symbol: "📚",
    href: "/future-books/ebooks",
  },
  {
    title: "Lesson Plan",
    desc: "Generate chapter lesson plans for Class 6 and 7 SST",
    symbol: "🗓️",
    href: "/future-books/lesson-plans",
  },
  {
    title: "Test Paper Generator",
    desc: "Create chapter-wise Social Science papers",
    symbol: "📝",
    href: "/future-books/generate",
  },
  {
    title: "Worksheets",
    desc: "Class 6 and Class 7 chapter practice sheets",
    symbol: "📄",
    href: "/future-books/worksheets",
  },
] as const;

export default function FutureBooksDashboardPage() {
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
          <Link href="/future-books/login" className="fb-btn fb-btn-outline">
            Log Out
          </Link>
        </div>
      </header>

      <main className="fb-main">
        <div className="fb-dash-intro">
          <div>
            <div className="fb-eyebrow">Future Books Learning Portal</div>
            <h1>Digital Contents</h1>
            <p>Explore our carefully arranged teaching and learning resources.</p>
          </div>
        </div>

        <div className="fb-dashboard-grid">
          {TILES.map((tile) => (
            <Link key={tile.title} href={tile.href} className="fb-tile">
              <span className="fb-symbol">{tile.symbol}</span>
              <span className="fb-tile-title">{tile.title}</span>
              <span className="fb-tile-desc">{tile.desc}</span>
              <span className="fb-tile-arrow">↗</span>
            </Link>
          ))}
        </div>
      </main>

      <footer className="fb-foot">© {new Date().getFullYear()} Future Books. Digital teaching and learning resources.</footer>
    </div>
  );
}
