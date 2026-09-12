"use client";

import { useEffect, useState } from "react";
import {
  CheckCircle2,
  Loader2,
  ChevronRight,
  ArrowLeft,
  BookOpen,
  ListChecks,
  Download,
  Languages,
  Calculator,
  Monitor,
  Leaf,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import { API_BASE, apiFetch } from "@/lib/api";

const QUESTIONS_PER_TYPE = 5;
const MATCH_TYPE_IDS = new Set(["word_match", "picture_match"]);

function questionsForType(typeId: string): number {
  return MATCH_TYPE_IDS.has(typeId) ? 1 : QUESTIONS_PER_TYPE;
}

interface Subject {
  id: number;
  name: string;
  display_name: string;
  icon?: string | null;
}

interface Chapter {
  id: string;
  number: number;
  title: string;
  start_page: number;
  end_page?: number | null;
}

const ICON_MAP: Record<string, LucideIcon> = {
  Languages,
  Calculator,
  Monitor,
  BookOpen,
  Leaf,
};

const SUBJECT_COLORS = [
  "border-blue-500 bg-blue-500/10 text-blue-400",
  "border-green-500 bg-green-500/10 text-green-400",
  "border-purple-500 bg-purple-500/10 text-purple-400",
  "border-amber-500 bg-amber-500/10 text-amber-400",
  "border-teal-500 bg-teal-500/10 text-teal-400",
];

const FORMAT_OPTIONS = [
  { id: "mcq", label: "Multiple Choice Questions (MCQ)" },
  { id: "assertion_reason", label: "Assertion and Reason" },
  { id: "true_false", label: "True / False" },
  { id: "fill_blank", label: "Fill in the Blanks" },
  { id: "word_match", label: "Match the Following — Words (5 pairs)", group: "match" as const },
  { id: "picture_match", label: "Match the Following — Pictures (5 pairs)", group: "match" as const },
  { id: "short_answer", label: "Short Answer (Subjective)" },
];

type Step = "subject" | "chapters" | "format" | "generating" | "complete" | "failed";

function subjectIcon(icon?: string | null): LucideIcon {
  if (icon && ICON_MAP[icon]) return ICON_MAP[icon];
  return Sparkles;
}

type SubjectSelectorProps = {
  initialSubjects?: Subject[];
  initialLoadError?: string;
};

export default function SubjectSelector({
  initialSubjects,
  initialLoadError,
}: SubjectSelectorProps) {
  const [step, setStep] = useState<Step>("subject");
  const [subjects, setSubjects] = useState<Subject[]>(initialSubjects ?? []);
  const [loadingSubjects, setLoadingSubjects] = useState(initialSubjects === undefined);
  const [selectedSubject, setSelectedSubject] = useState<Subject | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loadingChapters, setLoadingChapters] = useState(false);
  const [selectedChapterIds, setSelectedChapterIds] = useState<string[]>([]);
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState("");
  const [testId, setTestId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState(initialLoadError ?? "");

  useEffect(() => {
    if (initialSubjects !== undefined) {
      return;
    }
    (async () => {
      setLoadingSubjects(true);
      setErrorMsg("");
      try {
        const res = await apiFetch(`${API_BASE}/subjects`, { cache: "no-store" });
        if (!res.ok) throw new Error("Failed to load subjects");
        const data: Subject[] = await res.json();
        setSubjects(data);
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Failed to load subjects";
        setErrorMsg(
          msg === "Failed to fetch" || msg === "The operation was aborted."
            ? "Cannot reach the test API. Start the backend on port 8000, then refresh this page."
            : msg
        );
      } finally {
        setLoadingSubjects(false);
      }
    })();
  }, []);

  const loadChapters = async (subject: Subject) => {
    setLoadingChapters(true);
    setErrorMsg("");
    setSelectedSubject(subject);
    try {
      const res = await apiFetch(`${API_BASE}/subjects/${subject.id}/chapters`);
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to load chapters");
      }
      const data: Chapter[] = await res.json();
      setChapters(data);
      setSelectedChapterIds([]);
      setStep("chapters");
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Failed to load chapters");
      setSelectedSubject(null);
    } finally {
      setLoadingChapters(false);
    }
  };

  const toggleChapter = (id: string) => {
    setSelectedChapterIds((prev) =>
      prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]
    );
  };

  const toggleType = (id: string) => {
    setSelectedTypes((prev) =>
      prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]
    );
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
          questions_per_type: QUESTIONS_PER_TYPE,
          total_marks: 50,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to start generation");
      }

      const data = await res.json();
      pollStatus(data.task_id);
    } catch (e) {
      setStep("failed");
      setErrorMsg(e instanceof Error ? e.message : "Generation failed");
    }
  };

  const pollStatus = (taskId: string) => {
    let badPolls = 0;
    const maxBadPolls = 240;
    const interval = setInterval(async () => {
      try {
        const res = await apiFetch(`${API_BASE}/status/${taskId}`);

        if (res.status === 404) {
          clearInterval(interval);
          setStep("failed");
          setErrorMsg(
            "Generation was interrupted (server restarted). Please try again. If it keeps happening, pick fewer chapters or enable a persistent disk on Render."
          );
          return;
        }

        if (!res.ok) {
          badPolls += 1;
          if (res.status === 502 || res.status === 503) {
            setCurrentStep("Server busy or restarting — still trying…");
          }
          if (badPolls >= maxBadPolls) {
            clearInterval(interval);
            setStep("failed");
            setErrorMsg(
              `Could not reach the server (${res.status}). Generation can take 3–5 minutes on free hosting — wait and try again.`
            );
          }
          return;
        }

        badPolls = 0;
        const data = await res.json();
        setProgress(data.progress);
        if (data.current_step) setCurrentStep(data.current_step);

        if (data.status === "completed") {
          clearInterval(interval);
          if (data.result_id) {
            setTestId(String(data.result_id));
            sessionStorage.setItem("lastGeneratedTestId", String(data.result_id));
          }
          setStep("complete");
        } else if (data.status === "failed") {
          clearInterval(interval);
          setStep("failed");
          setErrorMsg(data.error_message || data.current_step || "Generation failed");
        }
      } catch {
        badPolls += 1;
        if (badPolls >= 45) {
          clearInterval(interval);
          setStep("failed");
          setErrorMsg("Lost connection while generating. Please try again.");
        }
      }
    }, 1000);
  };

  const downloadPdf = async (id: string) => {
    try {
      const res = await apiFetch(`${API_BASE}/test/${id}/pdf`);
      if (!res.ok) {
        let msg = "PDF download failed";
        try {
          const err = await res.json();
          if (typeof err.detail === "string" && err.detail) msg = err.detail;
        } catch {
          /* ignore */
        }
        setErrorMsg(msg);
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${selectedSubject?.name ?? "test"}_${id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "PDF download failed");
    }
  };

  const totalQuestions = selectedTypes.reduce(
    (n, typeId) => n + questionsForType(typeId),
    0
  );
  const marksPerQuestion =
    totalQuestions > 0 ? Math.floor(50 / totalQuestions) : 0;
  const extraMarkQuestions = totalQuestions > 0 ? 50 % totalQuestions : 0;

  if (step === "failed") {
    return (
      <div className="w-full max-w-2xl p-12 mx-auto text-center glass-card rounded-3xl">
        <h3 className="mb-4 text-2xl font-bold text-red-400">Generation Failed</h3>
        <p className="mb-8 text-gray-400">{errorMsg}</p>
        <button
          onClick={() => { setStep("format"); setErrorMsg(""); }}
          className="px-8 py-4 font-semibold text-black transition-colors bg-white rounded-xl hover:bg-gray-200"
        >
          Try Again
        </button>
      </div>
    );
  }

  if (step === "generating" || step === "complete") {
    return (
      <div className="w-full max-w-2xl p-12 mx-auto text-center glass-card rounded-3xl">
        {step === "complete" ? (
          <div className="flex flex-col items-center duration-500 animate-in fade-in zoom-in">
            <div className="flex items-center justify-center w-24 h-24 mb-6 text-green-500 rounded-full bg-green-500/20">
              <CheckCircle2 className="w-12 h-12" />
            </div>
            <h3 className="mb-2 text-3xl font-bold">Test Ready!</h3>
            <p className="mb-8 text-gray-400">
              {totalQuestions} questions · 50 marks total
              from {selectedSubject?.display_name}.
            </p>
            <div className="flex flex-col w-full gap-3 sm:flex-row sm:justify-center">
              <a
                href={`/test/${testId}`}
                className="px-8 py-4 font-semibold text-black transition-colors bg-white rounded-xl hover:bg-gray-200"
              >
                Take Test Online
              </a>
              <button
                onClick={() => testId && downloadPdf(testId)}
                className="inline-flex items-center justify-center gap-2 px-8 py-4 font-semibold text-white transition-colors bg-blue-600 rounded-xl hover:bg-blue-700"
              >
                <Download className="w-5 h-5" />
                Download PDF
              </button>
            </div>
            {errorMsg && (
              <p className="mt-4 text-sm text-red-400">{errorMsg}</p>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center w-full max-w-md mx-auto">
            <Loader2 className="w-16 h-16 mb-8 text-blue-500 animate-spin" />
            <h3 className="mb-2 text-2xl font-semibold">{currentStep}</h3>
            <div className="w-full h-3 mt-8 overflow-hidden rounded-full bg-white/10">
              <div
                className="h-full transition-all duration-500 ease-out bg-gradient-to-r from-blue-500 to-purple-500"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="w-full mt-3 text-right text-gray-400">{progress}%</p>
          </div>
        )}
      </div>
    );
  }

  if (step === "format") {
    return (
      <div className="w-full max-w-2xl mx-auto">
        <button
          onClick={() => setStep("chapters")}
          className="inline-flex items-center mb-6 text-sm text-gray-400 hover:text-white"
        >
          <ArrowLeft className="w-4 h-4 mr-1" /> Back to Chapters
        </button>
        <div className="p-8 glass-card rounded-3xl">
          <div className="flex items-center gap-3 mb-2">
            <ListChecks className="w-6 h-6 text-blue-400" />
            <h3 className="text-2xl font-bold">Select Question Formats</h3>
          </div>
          <p className="mb-6 text-gray-400">
            Pick the formats you want. Most formats give {QUESTIONS_PER_TYPE} questions.
            Match the Following is 1 question with 5 pairs.
          </p>

          <div className="space-y-3">
            {FORMAT_OPTIONS.map((opt) => (
              <label
                key={opt.id}
                className={`flex items-center gap-3 p-4 border rounded-xl cursor-pointer transition-colors ${
                  selectedTypes.includes(opt.id)
                    ? "border-blue-500 bg-blue-500/10"
                    : "border-white/10 hover:border-white/20"
                } ${opt.group === "match" ? "ml-4" : ""}`}
              >
                <input
                  type="checkbox"
                  checked={selectedTypes.includes(opt.id)}
                  onChange={() => toggleType(opt.id)}
                  className="w-4 h-4"
                />
                <span className="text-sm font-medium sm:text-base">{opt.label}</span>
              </label>
            ))}
          </div>

          {selectedTypes.length > 0 && (
            <p className="mt-4 text-sm text-blue-300">
              {totalQuestions} questions · 50 marks
              {extraMarkQuestions > 0
                ? ` (${marksPerQuestion}–${marksPerQuestion + 1} marks each)`
                : ` (${marksPerQuestion} marks each)`}
            </p>
          )}

          {errorMsg && <p className="mt-4 text-sm text-red-400">{errorMsg}</p>}

          <button
            onClick={handleGenerate}
            className="w-full px-10 py-4 mt-8 text-lg font-bold text-white transition-all bg-blue-600 rounded-xl hover:bg-blue-700"
          >
            Generate 50-Mark Test
          </button>
        </div>
      </div>
    );
  }

  if (step === "chapters") {
    return (
      <div className="w-full max-w-2xl mx-auto">
        <button
          onClick={() => { setStep("subject"); setSelectedSubject(null); }}
          className="inline-flex items-center mb-6 text-sm text-gray-400 hover:text-white"
        >
          <ArrowLeft className="w-4 h-4 mr-1" /> Back to Subjects
        </button>
        <div className="p-8 glass-card rounded-3xl">
          <div className="flex items-center gap-3 mb-2">
            <BookOpen className="w-6 h-6 text-green-400" />
            <h3 className="text-2xl font-bold">{selectedSubject?.display_name} — Chapters</h3>
          </div>
          <p className="mb-6 text-gray-400">
            Choose one or more chapters from the Class 1 textbook.
          </p>

          <div className="space-y-2 overflow-y-auto max-h-80">
            {chapters.map((ch) => (
              <label
                key={ch.id}
                className={`flex items-start gap-3 p-4 border rounded-xl cursor-pointer transition-colors ${
                  selectedChapterIds.includes(ch.id)
                    ? "border-green-500 bg-green-500/10"
                    : "border-white/10 hover:border-white/20"
                }`}
              >
                <input
                  type="checkbox"
                  checked={selectedChapterIds.includes(ch.id)}
                  onChange={() => toggleChapter(ch.id)}
                  className="mt-1 w-4 h-4"
                />
                <div>
                  <p className="font-semibold">{ch.title}</p>
                  <p className="text-xs text-gray-500">
                    Pages {ch.start_page}
                    {ch.end_page ? `–${ch.end_page}` : ""}
                  </p>
                </div>
              </label>
            ))}
          </div>

          <div className="flex gap-3 mt-6">
            <button
              onClick={() => setSelectedChapterIds(chapters.map((c) => c.id))}
              className="px-4 py-2 text-sm border rounded-lg border-white/10 hover:bg-white/5"
            >
              Select All
            </button>
            <button
              onClick={() => setSelectedChapterIds([])}
              className="px-4 py-2 text-sm border rounded-lg border-white/10 hover:bg-white/5"
            >
              Clear
            </button>
          </div>

          <button
            onClick={() => {
              if (selectedChapterIds.length === 0) {
                setErrorMsg("Select at least one chapter.");
                return;
              }
              setErrorMsg("");
              setSelectedTypes([]);
              setStep("format");
            }}
            className="flex items-center justify-center w-full gap-2 px-10 py-4 mt-8 text-lg font-bold text-white transition-all bg-blue-600 rounded-xl hover:bg-blue-700"
          >
            Continue to Formats
            <ChevronRight className="w-5 h-5" />
          </button>
          {errorMsg && <p className="mt-3 text-sm text-red-400">{errorMsg}</p>}
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-3xl mx-auto">
      <p className="mb-6 text-center text-gray-400">
        Select a Class 1 Semester 1 subject to begin.
      </p>

      {loadingSubjects ? (
        <div className="flex justify-center py-16">
          <Loader2 className="w-10 h-10 text-blue-500 animate-spin" />
        </div>
      ) : subjects.length === 0 ? (
        <p className="text-center text-red-400">{errorMsg || "No subjects available."}</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {subjects.map((subject, idx) => {
            const Icon = subjectIcon(subject.icon);
            const color = SUBJECT_COLORS[idx % SUBJECT_COLORS.length];
            const isLoading = loadingChapters && selectedSubject?.id === subject.id;

            return (
              <button
                key={subject.id}
                onClick={() => loadChapters(subject)}
                disabled={loadingChapters}
                className={`p-6 border-2 rounded-2xl flex flex-col items-center text-center transition-all duration-300 hover:-translate-y-1 disabled:opacity-60 ${color}`}
              >
                <div className={`p-4 mb-4 rounded-2xl ${color}`}>
                  {isLoading ? (
                    <Loader2 className="w-8 h-8 animate-spin" />
                  ) : (
                    <Icon className="w-8 h-8" />
                  )}
                </div>
                <h3 className="text-lg font-bold">{subject.display_name}</h3>
                <p className="mt-1 text-xs text-gray-400">Class 1 · Sem 1</p>
              </button>
            );
          })}
        </div>
      )}

      {errorMsg && !loadingSubjects && subjects.length > 0 && (
        <p className="mt-4 text-sm text-center text-red-400">{errorMsg}</p>
      )}
    </div>
  );
}
