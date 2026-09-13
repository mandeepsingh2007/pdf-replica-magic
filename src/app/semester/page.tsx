import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  CalendarCheck,
  Cpu,
  FileText,
  Layers,
  Sparkles,
} from "lucide-react";
import "./semester.css";

export const metadata: Metadata = {
  title: "Semester Book Digital Contents",
  description: "E-book, lesson plans, worksheets, and test generator for semester books.",
};

export default function SemesterPortalPage() {
  return (
    <div className="semester-portal">
      <header>
        <div className="nav-container">
          <Link href="/" className="brand">
            <div className="brand-icon">
              <Layers style={{ width: 22, height: 22 }} />
            </div>
            <span className="brand-title">Semester Book Digital Contents</span>
          </Link>
        </div>
      </header>

      <section className="hero">
        <div className="hero-badge">
          <Sparkles style={{ width: 14, height: 14 }} />
          Interactive Teacher & Student Portal
        </div>
        <h1>Empowering Smart Classrooms</h1>
        <p>
          Access all your curriculum-aligned learning materials, automated evaluation tools, and
          daily classroom resources in one place.
        </p>
      </section>

      <main>
        <div className="grid-container">
          <a href="#ebook" className="action-card">
            <div className="card-icon-wrapper ebook-color">
              <BookOpen style={{ width: 28, height: 28 }} />
            </div>
            <h2 className="card-title">E-Book</h2>
            <p className="card-desc">
              Flipbook edition with interactive audio, animations, and page zoom features.
            </p>
            <span className="card-btn">
              Open Reader <ArrowRight style={{ width: 16, height: 16 }} />
            </span>
          </a>

          <a href="#lesson-plan" className="action-card">
            <div className="card-icon-wrapper lesson-color">
              <CalendarCheck style={{ width: 28, height: 28 }} />
            </div>
            <h2 className="card-title">Lesson Plan</h2>
            <p className="card-desc">
              Detailed day-wise pedagogical plans, learning outcomes, and suggested activities.
            </p>
            <span className="card-btn">
              View Plans <ArrowRight style={{ width: 16, height: 16 }} />
            </span>
          </a>

          <a href="#worksheet" className="action-card">
            <div className="card-icon-wrapper worksheet-color">
              <FileText style={{ width: 28, height: 28 }} />
            </div>
            <h2 className="card-title">Worksheet</h2>
            <p className="card-desc">
              Printable chapter-wise assessment sheets with skill-building practice questions.
            </p>
            <span className="card-btn">
              Download PDF <ArrowRight style={{ width: 16, height: 16 }} />
            </span>
          </a>

          <Link href="/login" className="action-card">
            <div className="card-icon-wrapper test-color">
              <Cpu style={{ width: 28, height: 28 }} />
            </div>
            <h2 className="card-title">Test Generator</h2>
            <p className="card-desc">
              Create custom question papers, unit tests, and answer keys in seconds.
            </p>
            <span className="card-btn">
              Generate Paper <ArrowRight style={{ width: 16, height: 16 }} />
            </span>
          </Link>
        </div>
      </main>

      <footer>
        &copy; 2026 Semester Book Digital Contents. Designed for NEP & NCF Aligned Classrooms.
      </footer>
    </div>
  );
}
