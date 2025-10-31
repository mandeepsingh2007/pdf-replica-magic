import { useState, useEffect } from "react";

const navItems = [
  { id: "meet-us", label: "Meet Us" },
  { id: "cover-design", label: "Cover Design" },
  { id: "layout-design", label: "Layout Design" },
  { id: "illustrations", label: "Illustrations" },
  { id: "galore", label: "Galore" },
  { id: "corporate-design", label: "Corporate Design" },
  { id: "reach-us", label: "Reach Us" },
];

export const Navigation = () => {
  const [activeSection, setActiveSection] = useState("meet-us");

  useEffect(() => {
    const handleScroll = () => {
      const sections = navItems.map(item => document.getElementById(item.id));
      const scrollPosition = window.scrollY + 200;

      for (let i = sections.length - 1; i >= 0; i--) {
        const section = sections[i];
        if (section && section.offsetTop <= scrollPosition) {
          setActiveSection(navItems[i].id);
          break;
        }
      }
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollToSection = (id: string) => {
    const element = document.getElementById(id);
    if (element) {
      const offset = 80;
      const elementPosition = element.offsetTop - offset;
      window.scrollTo({ top: elementPosition, behavior: "smooth" });
    }
  };

  return (
    <nav className="fixed top-0 left-0 right-0 bg-white shadow-sm z-50">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex items-center justify-center py-4 text-sm">
          <span className="text-foreground mr-8">
            Color Code for our Blue Color (#00A0E3)
          </span>
        </div>
        <div className="flex items-center justify-center gap-8 pb-4 flex-wrap">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => scrollToSection(item.id)}
              className={`transition-colors ${
                activeSection === item.id
                  ? "text-foreground font-semibold"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
    </nav>
  );
};
