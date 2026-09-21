import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Baloo_2, Fredoka } from "next/font/google";
import "../../hindi.css";

const baloo = Baloo_2({ subsets: ["latin", "devanagari"], weight: ["500", "600", "700", "800"] });
const fredoka = Fredoka({ subsets: ["latin"], weight: ["400", "500", "600", "700"] });

const BOOKS: Record<string, { title: string; subtitle: string }> = {
  "01": {
    title: "हिंदी पाठमाला — पुस्तक 1",
    subtitle: "पन्ने पलटकर पढ़ें",
  },
  "02": {
    title: "हिंदी पाठमाला — पुस्तक 2",
    subtitle: "पन्ने पलटकर पढ़ें",
  },
};

type Props = {
  params: Promise<{ id: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const book = BOOKS[id];
  return {
    title: book ? `${book.title} | हिंदी पाठमाला` : "E-Book | हिंदी पाठमाला",
  };
}

export function generateStaticParams() {
  return Object.keys(BOOKS).map((id) => ({ id }));
}

export default async function HindiEbookReaderPage({ params }: Props) {
  const { id } = await params;
  const book = BOOKS[id];
  if (!book) notFound();

  return (
    <div className={`hindi-portal hp-reader-portal ${fredoka.className} ${baloo.className}`}>
      <div className="hp-reader-bar">
        <Link href="/hindi/ebooks" className="hp-back">
          ← किताबें
        </Link>
        <div className="hp-reader-title">
          <strong>{book.title}</strong>
          <span>{book.subtitle}</span>
        </div>
        <Link href="/hindi" className="hp-back">
          पोर्टल
        </Link>
      </div>
      <iframe
        className="hp-ebook-frame"
        title={book.title}
        src={`/hindi/ebooks/${id}/index.html`}
        allow="fullscreen"
      />
    </div>
  );
}
