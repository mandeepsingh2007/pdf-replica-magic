import type { Metadata } from "next";
import { NegraphicsHome } from "@/components/negraphics/NegraphicsHome";
import "./negraphics.css";

export const metadata: Metadata = {
  title: "NE Graphics",
  description:
    "Children's book design, layout, illustrations — and Semester Book digital test generator.",
};

export default function HomePage() {
  return (
    <div className="negraphics-site">
      <NegraphicsHome />
    </div>
  );
}
