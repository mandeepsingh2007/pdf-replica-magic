"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { API_BASE, apiFetch, readJson } from "@/lib/api";

type Chapter = { id: string; number: number; title: string };
type SubjectRow = { id: number; name: string; display_name: string };

const CLASS_META = [
  { level: 6, subjectName: "SST-6", label: "Class 6" },
  { level: 7, subjectName: "SST-7", label: "Class 7" },
] as const;

export default function FutureBooksLessonPlans() {
  const [classLevel, setClassLevel] = useState<(typeof CLASS_META)[number] | null>(null);
  const [subjectId, setSubjectId] = useState<number | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!classLevel) return;
    let cancelled = false;
    setLoading(true);
    setError("");
    setChapters([]);
    setSubjectId(null);

    (async () => {
      try {
        const res = await apiFetch(`${API_BASE}/subjects?track=future`);
        if (!res.ok) throw new Error("Could not load subjects.");
        const rows: SubjectRow[] = await readJson(res);
        const match = rows.find((row) => row.name === classLevel.subjectName);
        if (!match) {
          throw new Error(`${classLevel.label} Social Science textbook is not uploaded yet.`);
        }
        const chapterRes = await apiFetch(`${API_BASE}/subjects/${match.id}/chapters`);
        if (!chapterRes.ok) {
          const err = await readJson(chapterRes);
          throw new Error(err.detail || "Could not load chapters.");
        }
        const data: Chapter[] = await readJson(chapterRes);
        if (!cancelled) {
          setSubjectId(match.id);
          setChapters(data);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Could not load chapters.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [classLevel]);

  const generate = async (chapter: Chapter) => {
    if (!classLevel) return;
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
          class_level: classLevel.level,
          subject: "social_science",
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

  return (
    <div className="fb-section-panel">
      {!classLevel ? (
        <Link href="/future-books" className="fb-back">
          ← Back to Dashboard
        </Link>
      ) : (
        <button
          type="button"
          className="fb-back"
          onClick={() => {
            setClassLevel(null);
            setSubjectId(null);
            setChapters([]);
            setError("");
          }}
        >
          ← Back to Classes
        </button>
      )}

      <div className="fb-panel-top">
        <h2>
          {!classLevel
            ? "Lesson Plans — Choose a class"
            : `${classLevel.label} Social Science — Choose a chapter`}
        </h2>
      </div>
      <p>
        {!classLevel
          ? "Same lesson-plan template as Semester Books, filled from the Future Books SST chapter."
          : "Click Lesson Plan to download a chapter PDF."}
      </p>

      {error && <p className="fb-error">{error}</p>}
      {loading && <p>Loading…</p>}

      {!classLevel && (
        <div className="fb-choice-grid">
          {CLASS_META.map((item) => (
            <button key={item.level} type="button" className="fb-choice" onClick={() => setClassLevel(item)}>
              {item.label}
              <small>Social Science</small>
            </button>
          ))}
        </div>
      )}

      {classLevel && !loading && chapters.length > 0 && (
        <div className="fb-checks" style={{ maxHeight: "none" }}>
          {chapters.map((chapter) => (
            <div
              key={chapter.id}
              className="fb-check"
              style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}
            >
              <span>
                <strong>
                  Ch {chapter.number}. {chapter.title}
                </strong>
              </span>
              <button
                type="button"
                className="fb-btn"
                disabled={busyId !== null || subjectId == null}
                onClick={() => generate(chapter)}
              >
                {busyId === chapter.id ? "Making the plan…" : "Lesson Plan"}
              </button>
            </div>
          ))}
        </div>
      )}

      {classLevel && !loading && chapters.length === 0 && !error && (
        <p className="fb-error">No chapters found for this class yet.</p>
      )}
    </div>
  );
}
