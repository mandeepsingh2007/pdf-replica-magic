"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const navItems = [
  { id: "semester-book-portal", label: "Semester Book Portal" },
  { id: "hindi-pathmala-portal", label: "Hindi Pathmala" },
  { id: "meet-us", label: "Meet Us" },
  { id: "cover-design", label: "Cover Design" },
  { id: "layout-design", label: "Layout Design" },
  { id: "illustrations", label: "Illustrations" },
  { id: "galore", label: "Galore" },
  { id: "corporate-design", label: "Corporate Design" },
  { id: "reach-us", label: "Reach Us" },
];

export function Navigation() {
  const router = useRouter();
  const [activeSection, setActiveSection] = useState("semester-book-portal");

  useEffect(() => {
    const handleScroll = () => {
      const sections = navItems.map((item) => document.getElementById(item.id));
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

  const onNavClick = (id: string) => {
    if (id === "semester-book-portal") {
      router.push("/semester");
      return;
    }
    if (id === "hindi-pathmala-portal") {
      router.push("/hindi");
      return;
    }
    const element = document.getElementById(id);
    if (element) {
      const offset = 80;
      window.scrollTo({ top: element.offsetTop - offset, behavior: "smooth" });
    }
  };

  return (
    <nav className="fixed top-0 left-0 right-0 bg-white shadow-sm z-50">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex items-center justify-between py-4 text-sm">
          <img src="/negraphics/image.png" alt="Company Logo" className="h-16 w-auto" />
          <div className="flex items-center justify-center gap-8 flex-wrap">
            {navItems.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => onNavClick(item.id)}
                className={`transition-colors ${
                  activeSection === item.id
                    ? "ng-text-fg font-semibold"
                    : "ng-text-muted hover:ng-text-fg"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </nav>
  );
}
