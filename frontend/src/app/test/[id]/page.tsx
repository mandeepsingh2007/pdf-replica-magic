"use client";

import { useEffect, useState, useMemo, useCallback, type ReactNode } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, XCircle, Loader2, Award, Download } from "lucide-react";
import { API_BASE, apiFetch } from "@/lib/api";

interface QuestionDisplay {
  id: number;
  type: string;
  marks: number;
  section: string;
  display: Record<string, unknown>;
}

interface GradeResult {
  total_score: number;
  max_score: number;
  percentage: number;
  results: Array<{
    question_id: number;
    section: string;
    type: string;
    marks_awarded: number;
    max_marks: number;
    is_correct: boolean;
    user_answer: unknown;
    correct_answer: string;
    correction: string;
    pdf_excerpt: string;
    pdf_page_number?: number | null;
  }>;
}

type Answers = Record<string, string>;

const SECTION_KEYS = [
  "section_A_MCQs",
  "section_B_AssertionReason",
  "section_C_Objective",
  "section_D_MatchFollowing",
  "section_D_Subjective",
] as const;

function parseMatchAnswer(raw: string | undefined): Record<string, string> {
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object") {
      return Object.fromEntries(
        Object.entries(parsed).map(([k, v]) => [String(k), String(v)])
      );
    }
  } catch {
    /* not JSON */
  }
  return {};
}

function isQuestionAnswered(q: QuestionDisplay, answer: string | undefined): boolean {
  if (q.type === "word_match" || q.type === "picture_match") {
    const map = parseMatchAnswer(answer);
    const left = q.type === "picture_match"
      ? ((q.display as { pictures?: { key: string }[] }).pictures || [])
      : ((q.display as { column_a?: { key: string }[] }).column_a || []);
    const keys = left.length > 0 ? left.map((row) => row.key) : ["1", "2", "3", "4", "5"];
    return keys.every((k) => map[k] && map[k].length > 0);
  }
  return answer !== undefined && answer !== "";
}

function collectQuestions(testData: Record<string, QuestionDisplay[]>): QuestionDisplay[] {
  const all: QuestionDisplay[] = [];
  for (const key of SECTION_KEYS) {
    if (testData[key]) all.push(...testData[key]);
  }
  return all;
}

function MatchImage({ src, alt }: { src: string; alt: string }) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    apiFetch(src)
      .then((res) => (res.ok ? res.blob() : null))
      .then((blob) => {
        if (cancelled || !blob) return;
        objectUrl = URL.createObjectURL(blob);
        setBlobUrl(objectUrl);
      })
      .catch(() => setBlobUrl(null));

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [src]);

  if (!blobUrl) {
    return <div className="h-28 bg-gray-100 animate-pulse rounded-md sm:h-36" />;
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={blobUrl}
      alt={alt}
      className="block w-full max-w-[12rem] h-32 sm:h-40 mx-auto object-contain rounded-md bg-white"
    />
  );
}

function TraditionalMatchLayout({
  leftTitle,
  rightTitle,
  leftItems,
  rightItems,
  matchAns,
  disabled,
  onSelect,
}: {
  leftTitle: string;
  rightTitle: string;
  leftItems: { key: string; content: ReactNode }[];
  rightItems: { key: string; text: string }[];
  matchAns: Record<string, string>;
  disabled: boolean;
  onSelect: (leftKey: string, rightKey: string) => void;
}) {
  return (
    <div className="overflow-hidden border border-gray-200 rounded-xl">
      <div className="grid grid-cols-2 text-xs font-bold tracking-wide text-gray-600 uppercase bg-gray-100 border-b border-gray-200 sm:text-sm">
        <div className="px-3 py-2 border-r border-gray-200 sm:px-4">{leftTitle}</div>
        <div className="px-3 py-2 sm:px-4">{rightTitle}</div>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-0">
        <div className="border border-gray-200 divide-y divide-gray-100 rounded-lg sm:border-0 sm:rounded-none sm:border-r sm:divide-y">
          {leftItems.map((item) => (
            <div key={item.key} className="px-3 py-3 sm:px-4 sm:py-4 min-h-[7.5rem]">
              <div className="flex items-start gap-2">
                <span className="font-bold text-gray-800 shrink-0">({item.key})</span>
                <div className="min-w-0 flex-1">{item.content}</div>
              </div>
              <select
                value={matchAns[item.key] || ""}
                onChange={(e) => onSelect(item.key, e.target.value)}
                disabled={disabled}
                className="w-full px-2 py-1.5 mt-2 text-xs border border-gray-300 rounded-md bg-white sm:text-sm"
              >
                <option value="">Match →</option>
                {rightItems.map((opt) => (
                  <option key={opt.key} value={opt.key}>
                    ({opt.key}) {opt.text}
                  </option>
                ))}
              </select>
            </div>
          ))}
        </div>
        <div className="border border-gray-200 divide-y divide-gray-100 rounded-lg bg-gray-50/50 sm:border-0 sm:rounded-none sm:divide-y">
          {rightItems.map((opt) => (
            <div
              key={opt.key}
              className="flex items-start gap-2 px-3 py-3 text-sm leading-relaxed break-words min-h-[7.5rem] sm:px-4 sm:py-4 sm:text-base"
            >
              <span className="font-bold text-gray-800 shrink-0">({opt.key})</span>
              <span>{opt.text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function TestPaperPage() {
  const { id } = useParams();
  const [testMeta, setTestMeta] = useState<{
    title: string;
    subject_name: string;
    document_id?: number | null;
    total_marks: number;
    total_questions: number;
    test_data: Record<string, QuestionDisplay[]>;
  } | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [gradeResult, setGradeResult] = useState<GradeResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [grading, setGrading] = useState(false);
  const [error, setError] = useState("");
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  const downloadTestPdf = useCallback(async () => {
    if (!id || downloadingPdf) return;
    setDownloadingPdf(true);
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
        throw new Error(msg);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `test_${id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "PDF download failed");
    } finally {
      setDownloadingPdf(false);
    }
  }, [id, downloadingPdf]);

  const allQuestions = useMemo(
    () => (testMeta ? collectQuestions(testMeta.test_data) : []),
    [testMeta]
  );

  const answeredCount = useMemo(
    () =>
      allQuestions.filter((q) => isQuestionAnswered(q, answers[String(q.id)])).length,
    [allQuestions, answers]
  );

  const gradeMap = useMemo(() => {
    if (!gradeResult) return new Map();
    return new Map(gradeResult.results.map((r) => [r.question_id, r]));
  }, [gradeResult]);

  useEffect(() => {
    const fetchTest = async () => {
      try {
        const res = await apiFetch(`${API_BASE}/test/${id}/attempt`);
        if (!res.ok) throw new Error("Failed to load test");
        const data = await res.json();
        setTestMeta(data);
      } catch (err) {
        console.error(err);
        setError("Could not load test. Please try again.");
      } finally {
        setLoading(false);
      }
    };
    if (id) fetchTest();
  }, [id]);

  const submitAnswers = useCallback(async () => {
    if (grading || gradeResult) return;
    setGrading(true);
    setError("");
    try {
      const res = await apiFetch(`${API_BASE}/test/${id}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answers }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Grading failed");
      setGradeResult(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Grading failed");
    } finally {
      setGrading(false);
    }
  }, [answers, grading, gradeResult, id]);

  const setAnswer = (questionId: number, value: string) => {
    if (gradeResult) return;
    setAnswers((prev) => ({ ...prev, [String(questionId)]: value }));
  };

  const setMatchAnswer = (questionId: number, rowKey: string, colKey: string) => {
    if (gradeResult) return;
    const existing = parseMatchAnswer(answers[String(questionId)]);
    existing[rowKey] = colKey;
    setAnswers((prev) => ({
      ...prev,
      [String(questionId)]: JSON.stringify(existing),
    }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen gap-3 text-gray-600">
        <Loader2 className="w-6 h-6 animate-spin" />
        Loading Test Paper...
      </div>
    );
  }

  if (!testMeta) {
    return (
      <div className="flex items-center justify-center min-h-screen text-red-500">
        {error || "Test not found"}
      </div>
    );
  }

  const content = testMeta.test_data;

  return (
    <div className="min-h-screen px-3 py-4 pb-40 bg-gray-50 text-gray-900 sm:px-6 sm:py-8 sm:pb-48">
      <div className="max-w-4xl mx-auto">
        <div className="flex flex-col gap-2 mb-6 sm:flex-row sm:items-center sm:justify-between sm:mb-8">
          <Link href="/upload" className="inline-flex items-center text-gray-500 hover:text-blue-600">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Subjects
          </Link>
          <div className="flex items-center gap-3">
            <button
              onClick={downloadTestPdf}
              disabled={downloadingPdf}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-blue-700 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 disabled:opacity-50"
            >
              {downloadingPdf ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Download className="w-4 h-4" />
              )}
              Download PDF
            </button>
            {!gradeResult && (
              <span className="text-sm font-medium text-gray-500">
                Answered: {answeredCount} / {allQuestions.length}
              </span>
            )}
          </div>
        </div>

        {gradeResult && (
          <div className="p-8 mb-8 bg-white border-2 border-blue-200 shadow-lg rounded-2xl">
            <div className="flex flex-col items-center text-center">
              <Award className="w-16 h-16 mb-4 text-blue-600" />
              <h2 className="text-3xl font-bold">Your Score</h2>
              <p className="mt-2 text-5xl font-extrabold text-blue-600">
                {gradeResult.total_score}
                <span className="text-2xl text-gray-400"> / {gradeResult.max_score}</span>
              </p>
              <p className="mt-2 text-lg text-gray-500">{gradeResult.percentage}%</p>
              <p className="mt-4 text-sm text-gray-400">
                Graded against {testMeta.subject_name} textbook (PDF)
              </p>
            </div>
          </div>
        )}

        {grading && (
          <div className="flex items-center justify-center gap-3 p-6 mb-8 bg-blue-50 border border-blue-200 rounded-2xl">
            <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />
            <span className="font-medium text-blue-700">
              Checking answers against textbook…
            </span>
          </div>
        )}

        {error && (
          <div className="p-4 mb-8 text-red-700 bg-red-50 border border-red-200 rounded-xl">
            {error}
          </div>
        )}

        <div className="p-4 mb-6 bg-white border border-gray-200 shadow-sm rounded-2xl sm:p-8 sm:mb-8">
          <div className="text-center">
            <h1 className="text-xl font-bold uppercase tracking-wide sm:text-3xl sm:tracking-widest">{testMeta.title}</h1>
            <h2 className="mt-2 text-base font-medium text-gray-600 sm:text-xl">FINAL EXAMINATION</h2>
            <div className="flex flex-col gap-2 justify-between mt-6 text-xs font-bold text-gray-500 uppercase border-b-2 border-gray-200 pb-4 sm:flex-row sm:mt-8 sm:text-sm">
              <span>Time Allowed: 2 Hours</span>
              <span>Max Marks: {testMeta.total_marks}</span>
            </div>
          </div>
          <div className="mt-8 text-sm text-gray-600">
            <p className="mb-2"><strong>Instructions:</strong></p>
            <ul className="space-y-1 list-decimal list-inside">
              <li>Answer all questions below.</li>
              <li>Click <strong>Submit Test</strong> when finished — answers are not sent until you submit.</li>
              <li>Answers are verified against your subject textbook (PDF).</li>
            </ul>
          </div>
        </div>

        {content?.section_A_MCQs?.length > 0 && (
          <Section
            title="SECTION A: Multiple Choice Questions"
            questions={content.section_A_MCQs}
            renderQuestion={(q, i) => {
              const d = q.display as { question_text: string; options: string[] };
              const result = gradeMap.get(q.id);
              return (
                <QuestionCard
                  key={q.id}
                  number={i + 1}
                  marks={q.marks}
                  result={result}
                >
                  <p className="mb-4 text-base leading-relaxed break-words sm:text-lg">{d.question_text}</p>
                  <div className="grid grid-cols-1 gap-2 sm:gap-3 md:grid-cols-2">
                    {d.options.map((opt, j) => (
                      <label
                        key={j}
                        className={`flex items-center p-3 border rounded-lg cursor-pointer transition-colors ${
                          answers[String(q.id)] === opt
                            ? "border-blue-500 bg-blue-50"
                            : "border-gray-200 hover:border-gray-300"
                        } ${gradeResult ? "pointer-events-none" : ""}`}
                      >
                        <input
                          type="radio"
                          name={`q-${q.id}`}
                          value={opt}
                          checked={answers[String(q.id)] === opt}
                          onChange={() => setAnswer(q.id, opt)}
                          disabled={!!gradeResult}
                          className="mr-3"
                        />
                        <span className="mr-2 font-bold text-gray-400">
                          {String.fromCharCode(65 + j)}.
                        </span>
                        <span>{opt}</span>
                      </label>
                    ))}
                  </div>
                </QuestionCard>
              );
            }}
          />
        )}

        {content?.section_B_AssertionReason?.length > 0 && (
          <Section
            title="SECTION B: Assertion and Reason"
            subtitle="Direction: Choose the correct option for each Assertion-Reason pair."
            questions={content.section_B_AssertionReason}
            renderQuestion={(q, i) => {
              const d = q.display as {
                assertion: string;
                reason: string;
                options: { code: string; label: string }[];
              };
              const result = gradeMap.get(q.id);
              return (
                <QuestionCard key={q.id} number={i + 1} marks={q.marks} result={result}>
                  <p className="mb-2 text-base leading-relaxed break-words sm:text-lg">
                    <span className="font-bold">Assertion (A):</span> {d.assertion}
                  </p>
                  <p className="mb-4 text-base leading-relaxed break-words sm:text-lg">
                    <span className="font-bold">Reason (R):</span> {d.reason}
                  </p>
                  <div className="space-y-2 text-sm sm:text-base">
                    {d.options.map((opt) => (
                      <label
                        key={opt.code}
                        className={`flex items-start gap-2 p-3 border rounded-lg cursor-pointer ${
                          answers[String(q.id)] === opt.code
                            ? "border-blue-500 bg-blue-50"
                            : "border-gray-200"
                        } ${gradeResult ? "pointer-events-none" : ""}`}
                      >
                        <input
                          type="radio"
                          name={`q-${q.id}`}
                          value={opt.code}
                          checked={answers[String(q.id)] === opt.code}
                          onChange={() => setAnswer(q.id, opt.code)}
                          disabled={!!gradeResult}
                          className="mt-1 mr-3"
                        />
                        <span className="leading-relaxed break-words">
                          <strong>{opt.code}.</strong> {opt.label}
                        </span>
                      </label>
                    ))}
                  </div>
                </QuestionCard>
              );
            }}
          />
        )}

        {content?.section_C_Objective?.length > 0 && (() => {
          const trueFalseQs = content.section_C_Objective.filter((q) => q.type === "true_false");
          const fillBlankQs = content.section_C_Objective.filter((q) => q.type === "fill_blank");
          let cNumber = 0;

          return (
            <>
              {trueFalseQs.length > 0 && (
                <Section
                  title="SECTION C: True / False"
                  subtitle="State whether each statement is True or False."
                  questions={trueFalseQs}
                  renderQuestion={(q) => {
                    cNumber += 1;
                    const num = cNumber;
                    const d = q.display as { statement?: string };
                    const result = gradeMap.get(q.id);
                    return (
                      <QuestionCard key={q.id} number={num} marks={q.marks} result={result}>
                        <p className="mb-4 text-base leading-relaxed break-words sm:text-lg">
                          {d.statement}
                        </p>
                        <div className="grid grid-cols-2 gap-2 sm:flex sm:gap-3">
                          {["true", "false"].map((val) => (
                            <label
                              key={val}
                              className={`flex items-center justify-center px-4 py-3 border rounded-lg cursor-pointer capitalize text-sm font-medium sm:px-6 sm:text-base ${
                                answers[String(q.id)] === val
                                  ? "border-blue-500 bg-blue-50 text-blue-800"
                                  : "border-gray-200 bg-white"
                              } ${gradeResult ? "pointer-events-none" : ""}`}
                            >
                              <input
                                type="radio"
                                name={`q-${q.id}`}
                                value={val}
                                checked={answers[String(q.id)] === val}
                                onChange={() => setAnswer(q.id, val)}
                                disabled={!!gradeResult}
                                className="mr-2"
                              />
                              {val}
                            </label>
                          ))}
                        </div>
                      </QuestionCard>
                    );
                  }}
                />
              )}

              {fillBlankQs.length > 0 && (
                <Section
                  title="SECTION C: Fill in the Blanks"
                  questions={fillBlankQs}
                  renderQuestion={(q) => {
                    cNumber += 1;
                    const num = cNumber;
                    const d = q.display as { sentence_with_blank?: string };
                    const result = gradeMap.get(q.id);
                    return (
                      <QuestionCard key={q.id} number={num} marks={q.marks} result={result}>
                        <p className="mb-4 text-base leading-relaxed break-words sm:text-lg">
                          {d.sentence_with_blank}
                        </p>
                        <input
                          type="text"
                          value={answers[String(q.id)] || ""}
                          onChange={(e) => setAnswer(q.id, e.target.value)}
                          disabled={!!gradeResult}
                          placeholder="Type your answer"
                          className="w-full px-4 py-3 text-base border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </QuestionCard>
                    );
                  }}
                />
              )}
            </>
          );
        })()}

        {(content?.section_D_MatchFollowing?.length > 0 ||
          content?.section_D_Subjective?.length > 0) &&
          (() => {
            const matchQs = content.section_D_MatchFollowing || [];
            const wordMatchQs = matchQs.filter((q) => q.type === "word_match").slice(0, 1);
            const pictureMatchQs = matchQs
              .filter((q) => q.type === "picture_match")
              .slice(0, 1);
            const legacyQs = content.section_D_Subjective || [];
            let dNumber = 0;

            return (
              <>
                {wordMatchQs.length > 0 && (
                  <Section
                    title="SECTION D: Match the Following (Words)"
                    subtitle="Match each item in Column A with the correct option in Column B."
                    questions={wordMatchQs}
                    renderQuestion={(q) => {
                      dNumber += 1;
                      const num = dNumber;
                      const d = q.display as {
                        column_a: { key: string; text: string }[];
                        column_b: { key: string; text: string }[];
                      };
                      const matchAns = parseMatchAnswer(answers[String(q.id)]);
                      const result = gradeMap.get(q.id);
                      return (
                        <QuestionCard key={q.id} number={num} marks={q.marks} result={result}>
                          <TraditionalMatchLayout
                            leftTitle="Column A"
                            rightTitle="Column B"
                            leftItems={d.column_a.map((row) => ({
                              key: row.key,
                              content: (
                                <span className="text-sm leading-relaxed sm:text-base">{row.text}</span>
                              ),
                            }))}
                            rightItems={d.column_b}
                            matchAns={matchAns}
                            disabled={!!gradeResult}
                            onSelect={(leftKey, rightKey) =>
                              setMatchAnswer(q.id, leftKey, rightKey)
                            }
                          />
                        </QuestionCard>
                      );
                    }}
                  />
                )}

                {pictureMatchQs.length > 0 && (
                  <Section
                    title="SECTION D: Match the Picture with Text"
                    subtitle="Match each of the 5 pictures with the correct label. Column B is shuffled."
                    questions={pictureMatchQs}
                    renderQuestion={(q) => {
                      dNumber += 1;
                      const num = dNumber;
                      const d = q.display as {
                        pictures: { key: string; image_id?: number; caption: string }[];
                        labels: { key: string; text: string }[];
                      };
                      const matchAns = parseMatchAnswer(answers[String(q.id)]);
                      const result = gradeMap.get(q.id);
                      const docId = testMeta.document_id;
                      return (
                        <QuestionCard key={q.id} number={num} marks={q.marks} result={result}>
                          <TraditionalMatchLayout
                            leftTitle="Pictures"
                            rightTitle="Labels"
                            leftItems={d.pictures.map((pic) => {
                              const imgUrl =
                                pic.image_id && docId
                                  ? `${API_BASE}/${docId}/images/${pic.image_id}`
                                  : null;
                              return {
                                key: pic.key,
                                content: imgUrl ? (
                                  <MatchImage src={imgUrl} alt={pic.caption} />
                                ) : (
                                  <div className="flex items-center justify-center min-h-[5rem] px-2 text-xs text-center text-gray-500 bg-gray-100 rounded-md border border-dashed sm:text-sm">
                                    {pic.caption}
                                  </div>
                                ),
                              };
                            })}
                            rightItems={d.labels}
                            matchAns={matchAns}
                            disabled={!!gradeResult}
                            onSelect={(leftKey, rightKey) =>
                              setMatchAnswer(q.id, leftKey, rightKey)
                            }
                          />
                        </QuestionCard>
                      );
                    }}
                  />
                )}

                {legacyQs.length > 0 && (
                  <Section
                    title="SECTION D: Subjective Questions"
                    questions={legacyQs}
                    renderQuestion={(q, i) => {
                      const d = q.display as { question: string };
                      const result = gradeMap.get(q.id);
                      return (
                        <QuestionCard key={q.id} number={i + 1} marks={q.marks} result={result}>
                          <p className="mb-4 text-base leading-relaxed break-words sm:text-lg">
                            {d.question}
                          </p>
                          <textarea
                            value={answers[String(q.id)] || ""}
                            onChange={(e) => setAnswer(q.id, e.target.value)}
                            disabled={!!gradeResult}
                            placeholder="Write your answer here..."
                            rows={4}
                            className="w-full px-4 py-3 text-base border border-gray-300 rounded-lg resize-y focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                        </QuestionCard>
                      );
                    }}
                  />
                )}
              </>
            );
          })()}

        {!gradeResult && (
          <div className="fixed bottom-0 left-0 right-0 z-20 px-3 py-3 bg-white border-t border-gray-200 shadow-[0_-4px_20px_rgba(0,0,0,0.08)] sm:px-6 sm:py-4">
            <div className="flex flex-col items-stretch gap-3 max-w-4xl mx-auto sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-center text-gray-600 sm:text-left">
                Answered <strong>{answeredCount}</strong> of <strong>{allQuestions.length}</strong> questions
              </p>
              <button
                onClick={submitAnswers}
                disabled={grading || answeredCount < allQuestions.length}
                className={`w-full sm:w-auto px-8 py-3 text-base font-bold rounded-xl transition-all sm:text-lg ${
                  answeredCount === allQuestions.length && !grading
                    ? "bg-blue-600 hover:bg-blue-700 text-white shadow-lg"
                    : "bg-gray-200 text-gray-500 cursor-not-allowed"
                }`}
              >
                {grading ? "Checking…" : "Submit Test"}
              </button>
            </div>
            {answeredCount < allQuestions.length && (
              <p className="mt-2 text-xs text-center text-gray-400">
                Answer all questions to enable Submit.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Section({
  title,
  subtitle,
  questions,
  renderQuestion,
}: {
  title: string;
  subtitle?: string;
  questions: QuestionDisplay[];
  renderQuestion: (q: QuestionDisplay, index: number) => ReactNode;
}) {
  return (
    <div className="p-4 mb-6 bg-white border border-gray-200 shadow-sm rounded-2xl sm:p-8 sm:mb-8">
      <h3 className="pb-2 mb-4 text-lg font-bold leading-snug border-b sm:mb-6 sm:text-xl">{title}</h3>
      {subtitle && <p className="mb-4 text-sm italic leading-relaxed text-gray-600 sm:mb-6">{subtitle}</p>}
      <div className="space-y-6 sm:space-y-8">
        {questions.map((q, i) => renderQuestion(q, i))}
      </div>
    </div>
  );
}

function QuestionCard({
  number,
  marks,
  result,
  children,
}: {
  number: number;
  marks: number;
  result?: GradeResult["results"][0];
  children: ReactNode;
}) {
  return (
    <div
      className={`rounded-xl border p-4 sm:p-5 ${
        result
          ? result.is_correct
            ? "bg-green-50 border-green-200"
            : "bg-red-50 border-red-200"
          : "bg-gray-50/50 border-gray-100"
      }`}
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <span className="text-lg font-bold text-gray-900 shrink-0">{number}.</span>
        <span className="shrink-0 px-2.5 py-1 text-xs font-bold text-blue-700 bg-blue-50 border border-blue-200 rounded-md whitespace-nowrap">
          [{marks} mark{marks !== 1 ? "s" : ""}]
        </span>
      </div>
      <div className="min-w-0">
        {children}
        {result && (
          <div className="pt-4 mt-4 border-t border-gray-200">
            <div className="flex items-center gap-2 mb-2">
              {result.is_correct ? (
                <CheckCircle2 className="w-5 h-5 text-green-600" />
              ) : (
                <XCircle className="w-5 h-5 text-red-600" />
              )}
              <span
                className={`font-semibold ${
                  result.is_correct ? "text-green-700" : "text-red-700"
                }`}
              >
                {result.marks_awarded} / {result.max_marks} marks
              </span>
            </div>
            {!result.is_correct && (
              <div className="space-y-2 text-sm">
                <p>
                  <strong>Your answer:</strong>{" "}
                  {String(result.user_answer ?? "(no answer)")}
                </p>
                <p>
                  <strong>Correct answer:</strong> {result.correct_answer}
                </p>
                {result.correction && (
                  <p className="p-3 text-gray-700 bg-white rounded-lg border">
                    {result.correction}
                  </p>
                )}
                {result.pdf_excerpt && (
                  <div className="p-3 text-sm text-gray-700 bg-gray-50 rounded-lg border">
                    <strong>Textbook reference</strong>
                    {result.pdf_page_number != null && (
                      <span className="ml-1 text-blue-600">(Page {result.pdf_page_number})</span>
                    )}
                    <p className="mt-1 text-gray-600">{result.pdf_excerpt}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
