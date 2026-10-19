"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowRight, CalendarCheck, GraduationCap, Layers, Loader2 } from "lucide-react";
import { API_BASE, apiFetch, readJson } from "@/lib/api";
import "../semester.css";

const CLASSES = [1, 2, 3, 4, 5];

const SUBJECTS = [
  { key: "computer", label: "Computer", api: "Computer" },
  { key: "gk", label: "General Knowledge", api: "GK" },
  { key: "mathematics", label: "Mathematics", api: "Mathematics" },
  { key: "english", label: "English", api: "English" },
  { key: "evs", label: "Environmental Studies", api: "EVS" },
];

type Chapter = { id: string; number: number; title: string };
type SubjectRow = { id: number; name: string; description?: string | null };

export default function LessonPlans() {
  const [classLevel, setClassLevel] = useState<number | null>(null);
  const [subjectKey, setSubjectKey] = useState<string | null>(null);
  const [available, setAvailable] = useState<typeof SUBJECTS>([]);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");

  const subject = SUBJECTS.find((item) => item.key === subjectKey) ?? null;

  useEffect(() => {
    if (!classLevel) return;
    let cancelled = false;
    setLoading(true);
    setError("");
    setAvailable([]);
    setSubjectKey(null);
    setChapters([]);

    (async () => {
      try {
        const res = await apiFetch(`${API_BASE}/subjects?track=english`);
        if (!res.ok) throw new Error("Could not load subjects.");
        const rows: SubjectRow[] = await readJson(res);
        const found = SUBJECTS.filter((item) =>
          rows.some(
            (row) =>
              row.name === item.api &&
              (row.description || "").toLowerCase().includes(`class ${classLevel}`)
          )
        );
        if (cancelled) return;
        setAvailable(found);
        if (found.length === 0) {
          setError(`Class ${classLevel} textbook is not uploaded yet, so there are no subjects.`);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Could not load subjects.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [classLevel]);

  useEffect(() => {
    if (!classLevel || !subject) return;
    let cancelled = false;
    setLoading(true);
    setError("");
    setChapters([]);

    (async () => {
      try {
        const res = await apiFetch(`${API_BASE}/subjects?track=english`);
        if (!res.ok) throw new Error("Could not load subjects.");
        const rows: SubjectRow[] = await readJson(res);
        const match = rows.find(
          (row) =>
            row.name === subject.api &&
            (row.description || "").toLowerCase().includes(`class ${classLevel}`)
        );
        if (!match) {
          throw new Error(
            `Class ${classLevel} ${subject.label} textbook is not uploaded yet, so there is no chapter list.`
          );
        }
        const chapterRes = await apiFetch(`${API_BASE}/subjects/${match.id}/chapters`);
        if (!chapterRes.ok) {
          const err = await readJson(chapterRes);
          throw new Error(err.detail || "Could not load chapters.");
        }
        const data: Chapter[] = await readJson(chapterRes);
        if (!cancelled) setChapters(data);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Could not load chapters.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [classLevel, subject]);

  const generate = async (chapter: Chapter) => {
    if (!classLevel || !subjectKey) return;
    setError("");
    setBusyId(chapter.id);
    try {
      const headers = new Headers({ "Content-Type": "application/json" });
      if (window.location.hostname.includes("ngrok")) {
        headers.set("ngrok-skip-browser-warning", "true");
      }
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 180_000);
      const res = await fetch(`${API_BASE}/lesson-plans`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          class_level: classLevel,
          subject: subjectKey,
          chapter_id: chapter.id,
        }),
        signal: controller.signal,
      }).finally(() => clearTimeout(timer));
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Lesson plan could not be made." }));
        const detail = err.detail;
        throw new Error(typeof detail === "string" ? detail : "Lesson plan could not be made.");
      }
      const blob = await res.blob();
      const header = res.headers.get("Content-Disposition") || "";
      const named = /filename="([^"]+)"/.exec(header);
      const filename = named?.[1] || "lesson-plan.pdf";
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
    } catch (e) {
      setError(
        e instanceof Error && e.name === "AbortError"
          ? "This is taking too long. Try the chapter again."
          : e instanceof Error
            ? e.message
            : "Lesson plan could not be made."
      );
    } finally {
      setBusyId(null);
    }
  };

  let heading = "Choose your class";
  let back = () => setClassLevel(null);
  let backHref: string | null = "/semester";
  if (classLevel && subject) {
    heading = `Class ${classLevel} · ${subject.label} — Choose a chapter`;
    back = () => {
      setError("");
      setSubjectKey(null);
    };
    backHref = null;
  } else if (classLevel) {
    heading = `Class ${classLevel} — Choose a subject`;
    back = () => {
      setError("");
      setClassLevel(null);
    };
    backHref = null;
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
          <CalendarCheck style={{ width: 14, height: 14 }} />
          Lesson Plans
        </div>
        <h1>{heading}</h1>
      </section>

      <main>
        {backHref ? (
          <Link href={backHref} className="sem-back">
            <ArrowLeft style={{ width: 16, height: 16 }} /> Back
          </Link>
        ) : (
          <button type="button" className="sem-back" onClick={back}>
            <ArrowLeft style={{ width: 16, height: 16 }} /> Back
          </button>
        )}

        {error && <p className="sem-error">{error}</p>}
        {loading && <p className="card-desc">Loading…</p>}

        {!classLevel && (
          <div className="grid-container sem-grid">
            {CLASSES.map((level) => (
              <button key={level} type="button" className="action-card" onClick={() => setClassLevel(level)}>
                <div className="card-icon-wrapper lesson-color">
                  <GraduationCap style={{ width: 28, height: 28 }} />
                </div>
                <h2 className="card-title">Class {level}</h2>
                <span className="card-btn">
                  Open <ArrowRight style={{ width: 16, height: 16 }} />
                </span>
              </button>
            ))}
          </div>
        )}

        {classLevel && !subject && !loading && available.length > 0 && (
          <div className="grid-container sem-grid">
            {available.map((item) => (
              <button key={item.key} type="button" className="action-card" onClick={() => setSubjectKey(item.key)}>
                <div className="card-icon-wrapper ebook-color">
                  <CalendarCheck style={{ width: 28, height: 28 }} />
                </div>
                <h2 className="card-title">{item.label}</h2>
                <span className="card-btn">
                  Open <ArrowRight style={{ width: 16, height: 16 }} />
                </span>
              </button>
            ))}
          </div>
        )}

        {classLevel && subject && !loading && (
          <div className="sem-plan-list">
            {chapters.map((chapter) => (
              <div key={chapter.id} className="sem-plan-row">
                <h2>
                  Ch {chapter.number} {chapter.title}
                </h2>
                <button
                  type="button"
                  className="sem-plan-btn"
                  disabled={busyId !== null}
                  onClick={() => generate(chapter)}
                >
                  {busyId === chapter.id ? (
                    <>
                      <Loader2 className="spin" style={{ width: 16, height: 16 }} /> Making the plan
                    </>
                  ) : (
                    "Lesson Plan"
                  )}
                </button>
              </div>
            ))}
          </div>
        )}
      </main>

      <footer>
        &copy; 2026 Semester Book Digital Contents. Designed for NEP & NCF Aligned Classrooms.
      </footer>
    </div>
  );
}
