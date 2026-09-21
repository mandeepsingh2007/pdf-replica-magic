import type { Metadata } from "next";
import Link from "next/link";
import { Baloo_2, Fredoka } from "next/font/google";
import "./hindi.css";

const baloo = Baloo_2({ subsets: ["latin", "devanagari"], weight: ["500", "600", "700", "800"] });
const fredoka = Fredoka({ subsets: ["latin"], weight: ["400", "500", "600", "700"] });

export const metadata: Metadata = {
  title: "Hindi Pathmala Digital Contents | हिंदी पाठमाला",
};

export default function HindiPortalPage() {
  return (
    <div className={`hindi-portal ${fredoka.className} ${baloo.className}`}>
      <div className="hp-wrap">
        <header className="hp-header">
          <Link href="/" className="hp-brand">
            <div className="hp-logo">📚</div>
            <div>
              <span className="hp-kicker">प्राथमिक व माध्यमिक शिक्षा</span>
              <span className="hp-title">हिंदी पाठमाला</span>
            </div>
          </Link>
          <label className="hp-class">
            कक्षा
            <select defaultValue="1" aria-label="कक्षा चुनें">
              {Array.from({ length: 8 }, (_, i) => i + 1).map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
        </header>

        <section className="hp-hero">
          <span className="hp-badge">✨ आनंदमय एवं रोचक शिक्षण ✨</span>
          <h1 className="hp-h1">
            Hindi Pathmala <em>Digital Contents</em>
          </h1>
          <p className="hp-sub">हिंदी पाठमाला - डिजिटल पाठ्य सामग्री एवं सहायक उपकरण</p>
        </section>

        <div className="hp-grid">
          <div className="hp-card hp-card-ebook">
            <span className="hp-pill" style={{ background: "#ffd124" }}>
              इंटरैक्टिव किताब
            </span>
            <h2>E-Book</h2>
            <p>डिजिटल ई-पुस्तक पढ़ें ऑडियो उच्चारण, चित्र और पन्ना पलटने वाले आकर्षक अनुभव के साथ।</p>
            <Link href="/hindi/login?next=/hindi/ebooks" className="hp-btn hp-btn-yellow">
              पढ़ना शुरू करें (Open E-Book)
            </Link>
          </div>

          <div className="hp-card hp-card-video">
            <span className="hp-pill" style={{ background: "#38b6ff", color: "#fff" }}>
              एनिमेटेड वीडियो
            </span>
            <h2>Video Lessons</h2>
            <p>कविताओं का गायन, सचित्र रोचक कहानियाँ और हिंदी व्याकरण के मजेदार एनिमेटेड पाठ।</p>
            <Link href="/hindi/videos" className="hp-btn hp-btn-sky">
              वीडियो देखें (Watch Videos)
            </Link>
          </div>

          <div className="hp-card hp-card-test">
            <span className="hp-pill" style={{ background: "#55d462" }}>
              अभ्यास व प्रश्न-पत्र
            </span>
            <h2>Test Generator</h2>
            <p>कस्टम वर्कशीट, बहुविकल्पीय प्रश्न (MCQs) और परीक्षा प्रश्न-पत्र एक क्लिक में तैयार करें।</p>
            <Link href="/hindi/login" className="hp-btn hp-btn-coral">
              टेस्ट बनाएं (Create Test)
            </Link>
          </div>
        </div>

        <footer className="hp-foot">
          © 2026 Hindi Pathmala Digital Education • Designed for Little Explorers
        </footer>
      </div>
    </div>
  );
}
