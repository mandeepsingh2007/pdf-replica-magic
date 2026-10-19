import type { Metadata } from "next";
import LessonPlans from "./LessonPlans";

export const metadata: Metadata = {
  title: "Lesson Plan | Semester Book Digital Contents",
};

export default function SemesterLessonPlansPage() {
  return <LessonPlans />;
}
