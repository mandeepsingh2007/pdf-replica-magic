import type { Metadata } from "next";
import Link from "next/link";
import { Baloo_2, Fredoka } from "next/font/google";
import HindiVideoGallery, { type HindiVideoItem } from "@/components/HindiVideoGallery";
import "../hindi.css";

const baloo = Baloo_2({ subsets: ["latin", "devanagari"], weight: ["500", "600", "700", "800"] });
const fredoka = Fredoka({ subsets: ["latin"], weight: ["400", "500", "600", "700"] });

export const metadata: Metadata = {
  title: "Video Lessons | हिंदी पाठमाला",
};

const VIDEOS: HindiVideoItem[] = [
  {
    id: "lesson-1",
    title: "हिंदी पाठमाला — पाठ वीडियो",
    subtitle: "क्लिक करके देखें",
    src: "/hindi/videos/pathmala-lesson-1.mp4",
  },
  {
    id: "sabji",
    title: "सब्जी की टोकरी",
    subtitle: "हिंदी पाठमाला भाग-2 · पाठ 5",
    src: "/hindi/videos/sabji-ki-tokri.mp4",
  },
];

export default function HindiVideosPage() {
  return (
    <div className={`hindi-portal ${fredoka.className} ${baloo.className}`}>
      <div className="hp-wrap">
        <header className="hp-header">
          <Link href="/hindi" className="hp-brand">
            <div className="hp-logo">🎬</div>
            <div>
              <span className="hp-kicker">एनिमेटेड वीडियो</span>
              <span className="hp-title">Video Lessons</span>
            </div>
          </Link>
          <Link href="/hindi" className="hp-back">
            ← पोर्टल पर वापस
          </Link>
        </header>

        <section className="hp-hero hp-hero-sm">
          <span className="hp-badge">✨ दो पाठ वीडियो ✨</span>
          <h1 className="hp-h1">
            वीडियो <em>चुनें और देखें</em>
          </h1>
          <p className="hp-sub">किसी भी कार्ड पर क्लिक करें — वीडियो यहीं चलेगी।</p>
        </section>

        <HindiVideoGallery videos={VIDEOS} />

        <footer className="hp-foot">
          © 2026 Hindi Pathmala Digital Education • Designed for Little Explorers
        </footer>
      </div>
    </div>
  );
}
