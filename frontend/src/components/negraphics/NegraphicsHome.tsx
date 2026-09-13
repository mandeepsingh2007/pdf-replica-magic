"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CTAButton } from "./CTAButton";
import { Navigation } from "./Navigation";
import { SectionHeader } from "./SectionHeader";

const coverBooks = "/negraphics/Adobe Express - file.png";
const layoutBooks = "/negraphics/Adobe Express - file (1).png";
const illustrations = "/negraphics/illustrations.png";
const corporateDesignImage = "/negraphics/Screenshot 2025-10-31 203723.png";

const slideshowImages = [
  "/negraphics/neg_cover_11.jpg",
  "/negraphics/neg_cover_13.jpg",
  "/negraphics/neg_cover_3.jpg",
  "/negraphics/neg_cover_4.jpg",
  "/negraphics/neg_cover_5.jpg",
  "/negraphics/neg_cover_6.jpg",
];

const galoreLeftSlideshowImages = [
  "/negraphics/neg_cover_14.jpg",
  "/negraphics/neg_cover_15.jpg",
  "/negraphics/neg_cover_17.jpg",
];

const galoreRightSlideshowImages = [
  "/negraphics/neg_cover_22.jpg",
  "/negraphics/neg_cover_27.jpg",
  "/negraphics/neg_cover_30.jpg",
];

export function NegraphicsHome() {
  const router = useRouter();
  const [isLg, setIsLg] = useState(false);
  const [currentSlide, setCurrentSlide] = useState(0);
  const [currentGaloreLeftSlide, setCurrentGaloreLeftSlide] = useState(0);
  const [currentGaloreRightSlide, setCurrentGaloreRightSlide] = useState(0);

  const openSemesterPortal = () => router.push("/semester");

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1024px)");
    const update = () => setIsLg(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentSlide((prev) => (prev + 1) % slideshowImages.length);
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentGaloreLeftSlide((prev) => (prev + 1) % galoreLeftSlideshowImages.length);
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentGaloreRightSlide((prev) => (prev + 1) % galoreRightSlideshowImages.length);
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <>
      <Navigation />
      <main className="pt-20 lg:pt-32">
        <section
          id="semester-book-portal"
          className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-8 lg:mb-16"
        >
          <div className="border-2 lg:border-4 ng-border-primary">
            <div className="ng-bg-primary ng-text-primary-fg py-6 lg:py-8 px-4 lg:px-8 flex flex-col lg:flex-row items-center justify-between">
              <div className="flex-1 order-2 lg:order-1">
                <h2 className="text-2xl lg:text-4xl font-bold mb-2 lg:mb-4">Semester Book</h2>
                <h2 className="text-2xl lg:text-4xl font-bold mb-4 lg:mb-6">Digital Contents</h2>
                <p className="mb-3 lg:mb-4 max-w-2xl text-sm lg:text-base">
                  Curriculum-aligned e-books, lesson plans, worksheets, and an AI-powered test
                  generator for smart classrooms — built for NEP and NCF aligned teaching.
                </p>
                <p className="mb-6 lg:mb-8 max-w-2xl text-sm lg:text-base">
                  Teachers can sign in to create custom question papers, unit tests, and answer keys
                  from your semester book content in seconds.
                </p>
                <CTAButton onClick={openSemesterPortal}>OPEN PORTAL</CTAButton>
              </div>
              <div className="flex-shrink-0 lg:ml-8 mb-6 lg:mb-0 order-1 lg:order-2">
                <img
                  src={layoutBooks}
                  alt="Semester book digital portal"
                  className="w-64 lg:w-96 h-auto"
                  style={{
                    transform: isLg
                      ? "scale(2.5) translateX(-110px)"
                      : "scale(1.6) translateX(-60px)",
                  }}
                />
              </div>
            </div>
          </div>
        </section>

        <section id="meet-us" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-8 lg:mb-16">
          <div className="border-2 lg:border-4 ng-border-primary">
            <SectionHeader title="Meet Us" />
            <div className="p-4 lg:p-8 bg-white flex flex-col lg:flex-row gap-4 lg:gap-8">
              <div className="flex-1 space-y-3 lg:space-y-4 ng-text-fg text-sm lg:text-base">
                <p>
                  We are a team of creative thinkers, passionate designers, and enthusiastic
                  illustrators.
                </p>
                <p className="font-bold">
                  We are high skilled creative minds that are habitually involved in avant-garde
                  design and illustration for children&apos;s literature. We are specialist in
                  children&apos;s book design, illustration and layout.
                </p>
                <p>
                  Apart from school textbooks, storybooks, and activity books, we also make
                  educational and interactive posters, and puzzles for children.
                </p>
                <p>
                  We are effortless graphic design studio that could innovate splendid quality of
                  visuals in market competitive prices.
                </p>
                <p>
                  Our dedication for design also divergence into other forms of graphic design. We
                  offer graphic design services for corporate identity communication including logo,
                  stationery, brochure, poster, catalogue, flyer, standee, and the like.
                </p>
                <p>
                  So, whether you are starting up a new company, or eagerly want to establish your
                  brand identity, NE Graphics is here to make all your dreams come true.
                </p>
              </div>
              <div className="flex flex-col justify-center items-center text-2xl lg:text-4xl font-bold ng-text-fg leading-tight">
                <img
                  src={slideshowImages[currentSlide]}
                  alt="Our Work Slideshow"
                  className="w-full max-w-xs lg:w-96 h-auto object-contain"
                />
              </div>
            </div>
          </div>
        </section>

        <section id="cover-design" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-8 lg:mb-16">
          <div className="border-2 lg:border-4 ng-border-primary">
            <div className="ng-bg-primary ng-text-primary-fg py-6 lg:py-8 px-4 lg:px-8 flex flex-col lg:flex-row items-center justify-between gap-6 lg:gap-12">
              <div className="w-full lg:w-1/2 order-2 lg:order-1">
                <h2 className="text-2xl lg:text-4xl font-bold mb-2 lg:mb-4">ATTENTION-GRABBING</h2>
                <h2 className="text-2xl lg:text-4xl font-bold mb-4 lg:mb-6">COVERS DESIGNS</h2>
                <p className="mb-3 lg:mb-4 text-sm lg:text-base">
                  It&apos;s our passion for creating beautifully finished illustrations that enables us
                  to create books that are head and shoulders above the rest.
                </p>
                <p className="mb-6 lg:mb-8 text-sm lg:text-base">
                  For an extra special touch, we work with incredibly talented illustrators who can
                  produce stunning bespoke artwork to suit your needs.
                </p>
                <CTAButton>COVER GALORE</CTAButton>
              </div>
              <div className="w-full lg:w-1/2 flex items-center justify-center order-1 lg:order-2">
                <img
                  src={coverBooks}
                  alt="Book covers showcase"
                  className="w-full max-w-xs lg:max-w-none h-auto object-contain"
                  style={{
                    transform: isLg
                      ? "scale(2.5) translateX(-130px)"
                      : "scale(1.9) translateX(-60px)",
                  }}
                />
              </div>
            </div>
          </div>
        </section>

        <section id="layout-design" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-8 lg:mb-16">
          <div className="border-2 lg:border-4 ng-border-primary">
            <div className="ng-bg-primary ng-text-primary-fg py-6 lg:py-8 px-4 lg:px-8 flex flex-col lg:flex-row items-center justify-between">
              <div className="flex-1 order-2 lg:order-1">
                <h2 className="text-2xl lg:text-4xl font-bold mb-2 lg:mb-4">STUNNING BOOK PAGE</h2>
                <h2 className="text-2xl lg:text-4xl font-bold mb-4 lg:mb-6">LAYOUT DESIGN</h2>
                <p className="mb-6 lg:mb-8 max-w-2xl text-sm lg:text-base">
                  No matter how complex, we offer a full range of options to produce creative page
                  layout designs and stunning looking books.
                </p>
                <CTAButton>RECENT PROJECTS</CTAButton>
              </div>
              <div className="flex-shrink-0 lg:ml-8 mb-6 lg:mb-0 order-1 lg:order-2">
                <img
                  src={layoutBooks}
                  alt="Book layout examples"
                  className="w-64 lg:w-96 h-auto"
                  style={{
                    transform: isLg
                      ? "scale(2.5) translateX(-110px)"
                      : "scale(1.6) translateX(-60px)",
                  }}
                />
              </div>
            </div>
          </div>
        </section>

        <section id="illustrations" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-8 lg:mb-16">
          <div className="border-2 lg:border-4 ng-border-primary">
            <div className="ng-bg-primary ng-text-primary-fg py-6 lg:py-8 px-4 lg:px-8 flex flex-col lg:flex-row items-center justify-between">
              <div className="flex-1 order-2 lg:order-1">
                <h2 className="text-2xl lg:text-4xl font-bold mb-2 lg:mb-4">LIVELY ILLUSTRATIONS...</h2>
                <h2 className="text-2xl lg:text-4xl font-bold mb-4 lg:mb-6">VIVID COLOURING</h2>
                <p className="mb-6 lg:mb-8 max-w-2xl text-sm lg:text-base">
                  For an extra special touch, we work with incredibly talented illustrators who can
                  produce stunning and bespoke artwork to suit your needs.
                </p>
                <CTAButton>ART GALLERY</CTAButton>
              </div>
              <div className="flex-shrink-0 lg:ml-8 mb-6 lg:mb-0 order-1 lg:order-2">
                <img src={illustrations} alt="Illustration samples" className="w-64 lg:w-96 h-auto" />
              </div>
            </div>
          </div>
        </section>

        <section id="galore" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-8 lg:mb-16">
          <div className="border-2 lg:border-4 ng-border-primary">
            <div className="ng-bg-primary ng-text-primary-fg py-8 lg:py-16 px-4 lg:px-8">
              <h2 className="text-3xl lg:text-5xl font-bold text-center mb-8 lg:mb-12">THE GALORE TOUR</h2>
              <div className="flex flex-col lg:flex-row items-center justify-center gap-4 lg:gap-8">
                <div className="w-32 h-32 lg:w-48 lg:h-48 flex items-center justify-center order-1">
                  <img
                    src={galoreLeftSlideshowImages[currentGaloreLeftSlide]}
                    alt="Galore Left Slideshow"
                    className="w-full h-full object-contain"
                    style={{
                      transform: isLg ? "scale(1.6) translateX(-15px)" : "scale(1.2)",
                    }}
                  />
                </div>
                <div className="flex flex-col lg:flex-row gap-4 lg:gap-8 order-3 lg:order-2">
                  {["Cover", "Layout", "Illustrations"].map((label, i) => (
                    <div
                      key={label}
                      className="bg-white ng-text-primary rounded-lg p-4 lg:p-8 w-full lg:w-48 text-center"
                      style={{ transform: "translateY(-130px)" }}
                    >
                      <h3 className="text-xl lg:text-2xl font-bold">{label}</h3>
                      {i < 2 && <h3 className="text-xl lg:text-2xl font-bold">Design</h3>}
                    </div>
                  ))}
                </div>
                <div className="w-32 h-32 lg:w-48 lg:h-48 flex items-center justify-center order-2 lg:order-3">
                  <img
                    src={galoreRightSlideshowImages[currentGaloreRightSlide]}
                    alt="Galore Right Slideshow"
                    className="w-full h-full object-contain"
                    style={{
                      transform: isLg ? "scale(1.6) translateX(20px)" : "scale(1.2) translateY(251px)",
                    }}
                  />
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="corporate-design" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-8 lg:mb-16">
          <div className="border-2 lg:border-4 ng-border-primary">
            <div className="ng-bg-primary ng-text-primary-fg py-6 lg:py-8 px-4 lg:px-8">
              <h2 className="text-2xl lg:text-4xl font-bold mb-1 lg:mb-2">CREATIVE</h2>
              <h2 className="text-3xl lg:text-5xl font-bold mb-6 lg:mb-8">CORPORATE DESIGNING</h2>
              <div className="flex flex-col lg:flex-row gap-6 lg:gap-12 mb-6 lg:mb-8">
                <div className="flex-1 order-2 lg:order-1">
                  <h3 className="text-xl lg:text-2xl font-bold mb-3 lg:mb-4">DESIGN VALUE</h3>
                  <p className="mb-3 lg:mb-4 text-sm lg:text-base">
                    We work closely with our reputed clients on a year-round tailored program.
                  </p>
                  <ul className="space-y-1 lg:space-y-2 list-disc list-inside text-sm lg:text-base">
                    <li>Ad Campaign</li>
                    <li>Brand Identity</li>
                    <li>Business Cards</li>
                    <li>Stationary Design</li>
                    <li>Packaging Design</li>
                  </ul>
                </div>
                <div className="flex-1 flex items-center justify-center order-1 lg:order-2 mb-4 lg:mb-0">
                  <img
                    src={corporateDesignImage}
                    alt="Corporate Design Graphic"
                    className="max-w-full h-auto object-contain"
                  />
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="reach-us" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-8 lg:mb-16">
          <div className="border-2 lg:border-4 ng-border-primary">
            <SectionHeader title="Reach Us" />
            <div className="p-6 lg:p-12 bg-white text-center">
              <h3 className="text-2xl lg:text-3xl font-bold ng-text-fg mb-3 lg:mb-4">Get In Touch</h3>
              <p className="text-lg lg:text-xl ng-text-muted mb-6 lg:mb-8">
                Ready to bring your vision to life? Contact NE Graphics today!
              </p>
            </div>
          </div>
        </section>
      </main>
    </>
  );
}
