import type { Metadata } from "next";
import Link from "next/link";
import "../future-books.css";

export const metadata: Metadata = {
  title: "Future Books | Digital Contents",
};

type Props = {
  searchParams: Promise<{ error?: string }>;
};

export default async function FutureBooksLoginPage({ searchParams }: Props) {
  const { error } = await searchParams;
  const message =
    error === "invalid"
      ? "Incorrect User ID or password. Please try again."
      : error === "bad_request"
        ? "Invalid request. Please try again."
        : "";

  return (
    <div className="future-books">
      <header className="fb-header">
        <Link href="/" className="fb-brand">
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
        </div>
      </header>

      <main className="fb-main">
        <section className="fb-login-layout" aria-label="Login">
          <div>
            <div className="fb-hero">
              <div className="fb-eyebrow">Welcome to Future Books</div>
              <h1>
                Learning resources,
                <br />
                beautifully organised.
              </h1>
              <p>
                Your digital hub for textbooks, lesson plans, question papers, worksheets and
                answer keys.
              </p>
              <div className="fb-line" />
            </div>
            <div className="fb-login-art">
              <div className="fb-book-art" aria-hidden="true">
                📚
              </div>
              <div className="fb-floating-label">Explore • Teach • Inspire</div>
            </div>
          </div>

          <div className="fb-login-card">
            <h2>Teacher Login</h2>
            <p>Sign in to access the Future Books Digital Contents portal.</p>
            <form action="/api/future-login" method="post">
              <label className="fb-field">
                User ID
                <input
                  type="text"
                  name="id"
                  autoComplete="username"
                  placeholder="Enter your user ID"
                  required
                />
              </label>
              <label className="fb-field">
                Password
                <input
                  type="password"
                  name="password"
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  required
                />
              </label>
              <div className="fb-error" role="alert" aria-live="polite">
                {message}
              </div>
              <button type="submit" className="fb-btn fb-btn-full">
                Login to Dashboard →
              </button>
            </form>
          </div>
        </section>
      </main>

      <footer className="fb-foot">© {new Date().getFullYear()} Future Books. Digital teaching and learning resources.</footer>
    </div>
  );
}
