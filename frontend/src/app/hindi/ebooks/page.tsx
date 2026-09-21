import type { Metadata } from "next";
import Link from "next/link";
import { Baloo_2, Fredoka } from "next/font/google";
import HindiEbookGallery, { type HindiEbookItem } from "@/components/HindiEbookGallery";
import "../hindi.css";

const baloo = Baloo_2({ subsets: ["latin", "devanagari"], weight: ["500", "600", "700", "800"] });
const fredoka = Fredoka({ subsets: ["latin"], weight: ["400", "500", "600", "700"] });

export const metadata: Metadata = {
  title: "E-Books | हिंदी पाठमाला",
};

const BOOKS: HindiEbookItem[] = [
  {
    id: "01",
    title: "हिंदी पाठमाला — पुस्तक 1",
    subtitle: "इंटरैक्टिव ई-बुक · पन्ने पलटकर पढ़ें",
    cover: "/hindi/ebooks/01/shot.png",
  },
  {
    id: "02",
    title: "हिंदी पाठमाला — पुस्तक 2",
    subtitle: "इंटरैक्टिव ई-बुक · पन्ने पलटकर पढ़ें",
    cover: "/hindi/ebooks/02/shot.png",
  },
];

export default function HindiEbooksPage() {
  return (
    <div className={`hindi-portal ${fredoka.className} ${baloo.className}`}>
      <div className="hp-wrap">
        <header className="hp-header">
          <Link href="/hindi" className="hp-brand">
            <div className="hp-logo">📖</div>
            <div>
              <span className="hp-kicker">इंटरैक्टिव किताब</span>
              <span className="hp-title">E-Books</span>
            </div>
          </Link>
          <Link href="/hindi" className="hp-back">
            ← पोर्टल पर वापस
          </Link>
        </header>

        <section className="hp-hero hp-hero-sm">
          <span className="hp-badge">✨ दो ई-पुस्तकें ✨</span>
          <h1 className="hp-h1">
            किताब <em>चुनें और पढ़ें</em>
          </h1>
          <p className="hp-sub">किसी भी कार्ड पर क्लिक करें — ई-बुक खुल जाएगी।</p>
        </section>

        <HindiEbookGallery books={BOOKS} />

        <footer className="hp-foot">
          © 2026 Hindi Pathmala Digital Education • Designed for Little Explorers
        </footer>
      </div>
    </div>
  );
}
