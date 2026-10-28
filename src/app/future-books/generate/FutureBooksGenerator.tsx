"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { API_BASE, apiFetch, readJson } from "@/lib/api";

const MARK_OPTIONS = [10, 20, 30, 50] as const;
type MarkOption = (typeof MARK_OPTIONS)[number];

const FORMAT_OPTIONS = [
  { id: "mcq", label: "MCQ" },
  { id: "true_false", label: "True-False" },
  { id: "word_match", label: "Match the Column" },
  { id: "assertion_reason", label: "Assertion Reason" },
  { id: "picture_match", label: "Picture Study" },
  { id: "short_answer", label: "Short Answer Type" },
  { id: "long_answer", label: "Long Answer Type" },
  { id: "source_based", label: "Source Based Questions" },
  { id: "map_work", label: "Map Work" },
] as const;

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

type Step = "subject" | "class" | "chapters" | "format" | "generating" | "complete" | "failed";

const CLASS_META = [
  { level: 6, subjectName: "SST-6", label: "Class 6" },
  { level: 7, subjectName: "SST-7", label: "Class 7" },
] as const;

type Props = {
  initialSubjects: Subject[];
  initialLoadError?: string;
};

export default function FutureBooksGenerator({ initialSubjects, initialLoadError }: Props) {
  const [step, setStep] = useState<Step>("subject");
  const [subjects] = useState(initialSubjects);
  const [selectedClass, setSelectedClass] = useState<(typeof CLASS_META)[number] | null>(null);
  const [selectedSubject, setSelectedSubject] = useState<Subject | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [selectedChapterIds, setSelectedChapterIds] = useState<string[]>([]);
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [totalMarks, setTotalMarks] = useState<MarkOption>(50);
  const [schoolName, setSchoolName] = useState("");
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState("");
  const [testId, setTestId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState(initialLoadError ?? "");
  const [loadingChapters, setLoadingChapters] = useState(false);

  const availableClasses = CLASS_META.filter((item) =>
    subjects.some((subject) => subject.name === item.subjectName)
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
          setStep("chapters");
        }
      } catch (e) {
        if (!cancelled) {
          setErrorMsg(e instanceof Error ? e.message : "Could not load chapters.");
          setStep("class");
        }
      } finally {
        if (!cancelled) setLoadingChapters(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedSubject]);

  const pickClass = (item: (typeof CLASS_META)[number]) => {
    const subject = subjects.find((row) => row.name === item.subjectName) ?? null;
    if (!subject) {
      setErrorMsg(`${item.label} textbook is not uploaded yet.`);
      return;
    }
    setSelectedClass(item);
    setSelectedSubject(subject);
    setErrorMsg("");
  };

  const toggleChapter = (id: string) => {
    setSelectedChapterIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const toggleType = (id: string) => {
    setSelectedTypes((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const pollStatus = async (taskId: string) => {
    for (;;) {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      const res = await apiFetch(`${API_BASE}/status/${taskId}`);
      if (!res.ok) continue;
      const data = await readJson(res);
      if (data.progress != null) setProgress(data.progress);
      if (data.current_step) setCurrentStep(data.current_step);
      if (data.status === "completed") {
        const id = data.result_id ?? data.result?.test_id ?? data.test_id ?? null;
        if (id != null) setTestId(String(id));
        setStep("complete");
        return;
      }
      if (data.status === "failed") {
        setErrorMsg(data.error_message || data.current_step || "Generation failed");
        setStep("failed");
        return;
      }
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
      pollStatus(data.task_id);
    } catch (e) {
      setStep("failed");
      setErrorMsg(e instanceof Error ? e.message : "Generation failed");
    }
  };

  const downloadPdf = async (id: string, kind: "pdf" | "answer-key" = "pdf") => {
    const path = kind === "answer-key" ? `/test/${id}/answer-key` : `/test/${id}/pdf`;
    const res = await apiFetch(`${API_BASE}${path}`);
    if (!res.ok) {
      setErrorMsg("Could not download the PDF.");
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = kind === "answer-key" ? `AnswerKey_${id}.pdf` : `Test_${id}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fb-section-panel">
      {step === "subject" && (
        <>
          <Link href="/future-books" className="fb-back">
            ← Back to Dashboard
          </Link>
          <div className="fb-panel-top">
            <h2>Choose a subject</h2>
          </div>
          <p>Currently available for Future Books test generation.</p>
          {errorMsg && <p className="fb-error">{errorMsg}</p>}
          <div className="fb-choice-grid">
            <button type="button" className="fb-choice" onClick={() => setStep("class")}>
              Social Science
              <small>Classes 6 and 7</small>
            </button>
          </div>
        </>
      )}

      {step === "class" && (
        <>
          <button type="button" className="fb-back" onClick={() => setStep("subject")}>
            ← Back to Subjects
          </button>
          <div className="fb-panel-top">
            <h2>Social Science — Choose a class</h2>
          </div>
          <p>Only classes with an uploaded textbook are shown.</p>
          {errorMsg && <p className="fb-error">{errorMsg}</p>}
          {loadingChapters && <p>Loading chapters…</p>}
          <div className="fb-choice-grid">
            {availableClasses.length === 0 ? (
              <p className="fb-error">No Social Science textbooks are uploaded yet.</p>
            ) : (
              availableClasses.map((item) => (
                <button
                  key={item.level}
                  type="button"
                  className="fb-choice"
                  onClick={() => pickClass(item)}
                  disabled={loadingChapters}
                >
                  {item.label}
                  <small>Part 1 textbook</small>
                </button>
              ))
            )}
          </div>
        </>
      )}

      {step === "chapters" && selectedClass && (
        <>
          <button
            type="button"
            className="fb-back"
            onClick={() => {
              setSelectedSubject(null);
              setSelectedClass(null);
              setStep("class");
            }}
          >
            ← Back to Classes
          </button>
          <div className="fb-panel-top">
            <h2>
              {selectedClass.label} Social Science — Chapters
            </h2>
          </div>
          <p>Choose one or more chapters. Questions will come only from your selection.</p>
          {errorMsg && <p className="fb-error">{errorMsg}</p>}
          <div className="fb-checks">
            {chapters.map((chapter) => (
              <label
                key={chapter.id}
                className={`fb-check ${selectedChapterIds.includes(chapter.id) ? "is-on" : ""}`}
              >
                <input
                  type="checkbox"
                  checked={selectedChapterIds.includes(chapter.id)}
                  onChange={() => toggleChapter(chapter.id)}
                />
                <span>
                  <strong>
                    Ch {chapter.number}. {chapter.title}
                  </strong>
                  <small style={{ display: "block", marginTop: 4 }}>
                    Pages {chapter.start_page}
                    {chapter.end_page ? `–${chapter.end_page}` : ""}
                  </small>
                </span>
              </label>
            ))}
          </div>
          <div style={{ display: "flex", gap: 12, marginTop: 18 }}>
            <button
              type="button"
              className="fb-btn fb-btn-outline"
              onClick={() => setSelectedChapterIds(chapters.map((chapter) => chapter.id))}
            >
              Select All
            </button>
            <button
              type="button"
              className="fb-btn fb-btn-outline"
              onClick={() => setSelectedChapterIds([])}
            >
              Clear
            </button>
          </div>
          <button
            type="button"
            className="fb-btn"
            style={{ marginTop: 22 }}
            onClick={() => {
              if (selectedChapterIds.length === 0) {
                setErrorMsg("Select at least one chapter.");
                return;
              }
              setErrorMsg("");
              setSelectedTypes([]);
              setStep("format");
            }}
          >
            Continue to Formats →
          </button>
        </>
      )}

      {step === "format" && (
        <>
          <button type="button" className="fb-back" onClick={() => setStep("chapters")}>
            ← Back to Chapters
          </button>
          <div className="fb-panel-top">
            <h2>Select Question Formats</h2>
          </div>
          <p>Pick the formats for this Social Science paper.</p>
          {errorMsg && <p className="fb-error">{errorMsg}</p>}
          <div className="fb-checks">
            {FORMAT_OPTIONS.map((option) => (
              <label
                key={option.id}
                className={`fb-check ${selectedTypes.includes(option.id) ? "is-on" : ""}`}
              >
                <input
                  type="checkbox"
                  checked={selectedTypes.includes(option.id)}
                  onChange={() => toggleType(option.id)}
                />
                <span>{option.label}</span>
              </label>
            ))}
          </div>

          <label className="fb-field" style={{ marginTop: 22 }}>
            School name
            <input
              type="text"
              value={schoolName}
              maxLength={120}
              onChange={(event) => setSchoolName(event.target.value)}
              placeholder="Enter the school name"
            />
          </label>

          <p style={{ margin: "18px 0 0", fontWeight: 700, color: "var(--navy)" }}>Total marks</p>
          <div className="fb-mark-grid">
            {MARK_OPTIONS.map((marks) => (
              <button
                key={marks}
                type="button"
                className={`fb-mark ${totalMarks === marks ? "selected" : ""}`}
                onClick={() => setTotalMarks(marks)}
              >
                {marks} Marks
                <small>
                  {marks === 10
                    ? "Quick Check"
                    : marks === 20
                      ? "Short Test"
                      : marks === 30
                        ? "Unit Test"
                        : "Full Test"}
                </small>
              </button>
            ))}
          </div>

          <button type="button" className="fb-btn" style={{ marginTop: 24 }} onClick={handleGenerate}>
            Generate {totalMarks}-Mark Test
          </button>
        </>
      )}

      {(step === "generating" || step === "complete" || step === "failed") && (
        <div style={{ textAlign: "center", padding: "24px 0" }}>
          {step === "generating" && (
            <>
              <h2 style={{ fontFamily: "Georgia, serif", color: "var(--navy)" }}>{currentStep}</h2>
              <p>{progress}%</p>
            </>
          )}
          {step === "failed" && (
            <>
              <h2 style={{ color: "#b63542" }}>Generation Failed</h2>
              <p className="fb-error">{errorMsg}</p>
              <button type="button" className="fb-btn" onClick={() => setStep("format")}>
                Try Again
              </button>
            </>
          )}
          {step === "complete" && (
            <>
              <h2 style={{ fontFamily: "Georgia, serif", color: "var(--navy)" }}>Test Ready!</h2>
              <p>
                {totalMarks} marks · {selectedClass?.label} Social Science
              </p>
              {errorMsg && <p className="fb-error">{errorMsg}</p>}
              {!testId && (
                <p className="fb-error">Test finished but no download id came back. Generate again.</p>
              )}
              {testId && (
                <div
                  style={{
                    display: "flex",
                    gap: 12,
                    justifyContent: "center",
                    flexWrap: "wrap",
                    marginTop: 18,
                  }}
                >
                  <Link href={`/test/${testId}`} className="fb-btn">
                    Take Test Online (with automated checking)
                  </Link>
                  <button type="button" className="fb-btn fb-btn-outline" onClick={() => downloadPdf(testId)}>
                    Download PDF
                  </button>
                  <button
                    type="button"
                    className="fb-btn fb-btn-outline"
                    onClick={() => downloadPdf(testId, "answer-key")}
                  >
                    Download Answer Key
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
