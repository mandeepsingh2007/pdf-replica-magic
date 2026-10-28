"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { API_BASE, apiFetch, readJson } from "@/lib/api";

type Subject = {
  id: number;
  name: string;
  display_name: string;
  description?: string | null;
};

type Chapter = {
  id: string;
  number: number;
  title: string;
  start_page: number;
  end_page?: number | null;
};

const MARK_OPTIONS = [25, 60, 80] as const;
type MarkOption = (typeof MARK_OPTIONS)[number];

const FORMAT_OPTIONS = [
  { id: "mcq", label: "Multiple Choice Questions (MCQ)" },
  { id: "true_false", label: "True / False" },
  { id: "word_match", label: "Match the Column" },
  { id: "assertion_reason", label: "Assertion Reason" },
  { id: "picture_match", label: "Picture Study" },
  { id: "short_answer", label: "Short Answer Type" },
  { id: "long_answer", label: "Long Answer Type" },
  { id: "source_based", label: "Source Based Questions" },
  { id: "map_work", label: "Map Work" },
];

const CLASS_SUBJECTS = [
  { classLevel: 6, name: "SST-6", label: "Class 6" },
  { classLevel: 7, name: "SST-7", label: "Class 7" },
] as const;

type Step = "subject" | "class" | "chapters" | "format" | "generating" | "complete" | "failed";

export default function FutureBooksWizard({
  initialSubjects,
  initialError,
}: {
  initialSubjects: Subject[];
  initialError?: string;
}) {
  const [step, setStep] = useState<Step>("subject");
  const [subjects] = useState(initialSubjects);
  const [selectedClass, setSelectedClass] = useState<(typeof CLASS_SUBJECTS)[number] | null>(null);
  const [selectedSubject, setSelectedSubject] = useState<Subject | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [selectedChapterIds, setSelectedChapterIds] = useState<string[]>([]);
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [totalMarks, setTotalMarks] = useState<MarkOption>(60);
  const [schoolName, setSchoolName] = useState("");
  const [loadingChapters, setLoadingChapters] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState("");
  const [testId, setTestId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState(initialError ?? "");

  const availableClasses = useMemo(
    () =>
      CLASS_SUBJECTS.filter((item) =>
        subjects.some((subject) => subject.name === item.name)
      ),
    [subjects]
  );

  useEffect(() => {
    if (!selectedSubject) return;
    let cancelled = false;
    setLoadingChapters(true);
    setErrorMsg("");
    (async () => {
      try {
        const res = await apiFetch(`${API_BASE}/subjects/${selectedSubject.id}/chapters`);
        if (!res.ok) throw new Error("Could not load chapters.");
        const rows: Chapter[] = await readJson(res);
        if (!cancelled) {
          setChapters(rows);
          setSelectedChapterIds([]);
        }
      } catch (e) {
        if (!cancelled) setErrorMsg(e instanceof Error ? e.message : "Could not load chapters.");
      } finally {
        if (!cancelled) setLoadingChapters(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedSubject]);

  const pollStatus = async (taskId: string) => {
    for (;;) {
      const res = await apiFetch(`${API_BASE}/status/${taskId}`);
      if (!res.ok) throw new Error("Could not check generation status.");
      const data = await readJson(res);
      setProgress(Number(data.progress ?? 0));
      if (data.current_step) setCurrentStep(data.current_step);
      if (data.status === "completed") {
        setTestId(String(data.result_id ?? data.test_id ?? ""));
        setStep("complete");
        return;
      }
      if (data.status === "failed") {
        throw new Error(data.error_message || data.current_step || "Generation failed");
      }
      await new Promise((resolve) => setTimeout(resolve, 1500));
    }
  };

  const handleGenerate = async () => {
    if (!selectedSubject) return;
    if (selectedChapterIds.length === 0) {
      setErrorMsg("Select at least one chapter.");
      return;
    }
    if (selectedTypes.length === 0) {
      setErrorMsg("Select at least one question format.");
      return;
    }
    const school = schoolName.trim().replace(/\s+/g, " ");
    if (!school) {
      setErrorMsg("Enter the school name.");
      return;
    }

    setStep("generating");
    setErrorMsg("");
    setProgress(0);
    setCurrentStep("Starting generation…");

    try {
      const res = await apiFetch(`${API_BASE}/generate-test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          subject_id: selectedSubject.id,
          chapter_ids: selectedChapterIds,
          include_types: selectedTypes,
          questions_per_type: 5,
          total_marks: totalMarks,
          school_name: school,
        }),
      });
      if (!res.ok) {
        const err = await readJson(res);
        throw new Error(err.detail || "Failed to start generation");
      }
      const data = await readJson(res);
      await pollStatus(data.task_id);
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Generation failed");
      setStep("failed");
    }
  };

  return (
    <div className="section-panel">
      {step !== "subject" && step !== "generating" && step !== "complete" && (
        <button
          type="button"
          className="back"
          onClick={() => {
            setErrorMsg("");
            if (step === "class") setStep("subject");
            else if (step === "chapters") {
              setSelectedClass(null);
              setSelectedSubject(null);
              setStep("class");
            } else if (step === "format") setStep("chapters");
            else if (step === "failed") setStep("format");
          }}
        >
          ← Back
        </button>
      )}

      {errorMsg && <p className="error">{errorMsg}</p>}

      {step === "subject" && (
        <>
          <div className="panel-top">
            <h2>Choose a subject</h2>
          </div>
          <p>Select the subject for your test paper.</p>
          <div className="choice-grid">
            <button
              type="button"
              className="choice"
              onClick={() => {
                setStep("class");
                setErrorMsg("");
              }}
            >
              Social Science
              <small>Classes 6 and 7</small>
            </button>
          </div>
        </>
      )}

      {step === "class" && (
        <>
          <div className="panel-top">
            <h2>Social Science — Choose a class</h2>
          </div>
          <p>Only classes with an uploaded textbook are shown.</p>
          {availableClasses.length === 0 ? (
            <p className="error">Class 6 and Class 7 Social Science books are not seeded yet.</p>
          ) : (
            <div className="choice-grid">
              {availableClasses.map((item) => (
                <button
                  key={item.name}
                  type="button"
                  className="choice"
                  onClick={() => {
                    const subject = subjects.find((row) => row.name === item.name) ?? null;
                    setSelectedClass(item);
                    setSelectedSubject(subject);
                    setStep("chapters");
                  }}
                >
                  {item.label}
                  <small>Social Science</small>
                </button>
              ))}
            </div>
          )}
        </>
      )}

      {step === "chapters" && (
        <>
          <div className="panel-top">
            <h2>
              {selectedClass?.label} Social Science — Chapters
            </h2>
          </div>
          <p>Choose one or more chapters from the textbook.</p>
          {loadingChapters ? (
            <p>Loading chapters…</p>
          ) : (
            <div className="checks">
              {chapters.map((chapter) => {
                const on = selectedChapterIds.includes(chapter.id);
                return (
                  <label key={chapter.id} className={on ? "is-on" : ""}>
                    <input
                      type="checkbox"
                      checked={on}
                      onChange={() =>
                        setSelectedChapterIds((prev) =>
                          on ? prev.filter((id) => id !== chapter.id) : [...prev, chapter.id]
                        )
                      }
                    />
                    <span>
                      <strong>
                        Ch {chapter.number} {chapter.title}
                      </strong>
                      <br />
                      <small>
                        Pages {chapter.start_page}
                        {chapter.end_page ? `–${chapter.end_page}` : ""}
                      </small>
                    </span>
                  </label>
                );
              })}
            </div>
          )}
          <button
            type="button"
            className="btn"
            style={{ marginTop: 24 }}
            onClick={() => {
              if (selectedChapterIds.length === 0) {
                setErrorMsg("Select at least one chapter.");
                return;
              }
              setErrorMsg("");
              setStep("format");
            }}
          >
            Continue to Formats →
          </button>
        </>
      )}

      {step === "format" && (
        <>
          <div className="panel-top">
            <h2>Select Question Formats</h2>
          </div>
          <p>Pick the formats for this Social Science paper.</p>
          <div className="checks">
            {FORMAT_OPTIONS.map((opt) => {
              const on = selectedTypes.includes(opt.id);
              return (
                <label key={opt.id} className={on ? "is-on" : ""}>
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={() =>
                      setSelectedTypes((prev) =>
                        on ? prev.filter((id) => id !== opt.id) : [...prev, opt.id]
                      )
                    }
                  />
                  <span>{opt.label}</span>
                </label>
              );
            })}
          </div>

          <label className="field" style={{ marginTop: 24 }}>
            School name
            <input
              type="text"
              value={schoolName}
              maxLength={120}
              onChange={(event) => setSchoolName(event.target.value)}
              placeholder="Enter the school name"
            />
          </label>

          <p style={{ marginTop: 24, fontWeight: 700, color: "var(--navy)" }}>Total marks</p>
          <div className="mark-grid">
            {MARK_OPTIONS.map((marks) => (
              <button
                key={marks}
                type="button"
                className={`mark ${totalMarks === marks ? "selected" : ""}`}
                onClick={() => setTotalMarks(marks)}
              >
                {marks}
                <small>
                  {marks === 25
                    ? "Short Assessment"
                    : marks === 60
                      ? "Term Assessment"
                      : "Full-Length Assessment"}
                </small>
              </button>
            ))}
          </div>

          <button type="button" className="btn full" style={{ marginTop: 28 }} onClick={handleGenerate}>
            Generate {totalMarks}-Mark Test
          </button>
        </>
      )}

      {step === "generating" && (
        <>
          <div className="panel-top">
            <h2>{currentStep || "Generating…"}</h2>
          </div>
          <p>{progress}% complete</p>
        </>
      )}

      {step === "complete" && (
        <>
          <div className="panel-top">
            <h2>Test Ready!</h2>
          </div>
          <p>
            {totalMarks}-mark Social Science paper for {selectedClass?.label}.
          </p>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 20 }}>
            {testId ? (
              <Link href={`/test/${testId}`} className="btn">
                Take Test Online
              </Link>
            ) : null}
            <button type="button" className="btn btn-outline" onClick={() => setStep("subject")}>
              Create Another
            </button>
          </div>
        </>
      )}

      {step === "failed" && (
        <>
          <div className="panel-top">
            <h2>Generation Failed</h2>
          </div>
          <button type="button" className="btn" onClick={() => setStep("format")}>
            Try Again
          </button>
        </>
      )}
    </div>
  );
}
