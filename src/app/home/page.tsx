import Link from 'next/link';
import { ArrowRight, BookOpen, BrainCircuit, FileCode2 } from 'lucide-react';

export default function Home() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-background">
      {/* Background Ambient Orbs */}
      <div className="absolute top-0 -left-4 w-72 h-72 bg-blue-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob"></div>
      <div className="absolute top-0 -right-4 w-72 h-72 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000"></div>
      <div className="absolute -bottom-8 left-20 w-72 h-72 bg-indigo-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-4000"></div>

      <main className="relative z-10 flex flex-col items-center justify-center min-h-screen px-4 text-center">
        
        <div className="inline-flex items-center gap-2 px-3 py-1 mb-8 text-sm font-medium border rounded-full glassmorphism text-primary-100 border-white/10">
          <span className="flex w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
          Production-Grade AI Generator
        </div>

        <h1 className="max-w-4xl mb-6 text-5xl font-extrabold tracking-tight sm:text-7xl">
          Generate <span className="text-gradient">Custom Tests</span> in Seconds
        </h1>
        
        <p className="max-w-2xl mb-10 text-lg text-gray-400 sm:text-xl">
          Class 1 Semester 1 textbooks — English, Maths, Computer, GK &amp; EVS. Pick chapters and formats, get 5 fresh questions per category.
        </p>

        <div className="flex flex-col gap-4 sm:flex-row">
          <Link href="/upload" className="inline-flex items-center justify-center px-8 py-4 text-base font-semibold text-white transition-all duration-200 bg-blue-600 border border-transparent rounded-xl hover:bg-blue-700 shadow-[0_0_20px_rgba(37,99,235,0.4)]">
            Start Generating
            <ArrowRight className="w-5 h-5 ml-2" />
          </Link>
          <Link href="#features" className="inline-flex items-center justify-center px-8 py-4 text-base font-semibold text-white transition-all duration-200 border rounded-xl glassmorphism hover:bg-white/5">
            View Sample Paper
          </Link>
        </div>

        {/* Feature Highlights */}
        <div className="grid grid-cols-1 gap-6 mt-24 sm:grid-cols-3 max-w-7xl">
          <div className="p-6 text-left transition-all duration-300 glass-card rounded-2xl hover:translate-y--1">
            <div className="flex items-center justify-center w-12 h-12 mb-4 rounded-lg bg-blue-500/20 text-blue-400">
              <BrainCircuit className="w-6 h-6" />
            </div>
            <h3 className="mb-2 text-xl font-semibold">Multimodal AI</h3>
            <p className="text-sm text-gray-400">Understands diagrams and images for 'Picture Matching' questions natively.</p>
          </div>
          <div className="p-6 text-left transition-all duration-300 glass-card rounded-2xl hover:translate-y--1">
            <div className="flex items-center justify-center w-12 h-12 mb-4 rounded-lg bg-purple-500/20 text-purple-400">
              <FileCode2 className="w-6 h-6" />
            </div>
            <h3 className="mb-2 text-xl font-semibold">Layout-Aware</h3>
            <p className="text-sm text-gray-400">Doesn't just read text blindly. Perfectly parses complex tables and multicolumn PDFs.</p>
          </div>
          <div className="p-6 text-left transition-all duration-300 glass-card rounded-2xl hover:translate-y--1">
            <div className="flex items-center justify-center w-12 h-12 mb-4 rounded-lg bg-indigo-500/20 text-indigo-400">
              <BookOpen className="w-6 h-6" />
            </div>
            <h3 className="mb-2 text-xl font-semibold">Fresh Every Time</h3>
            <p className="text-sm text-gray-400">5 unique questions per format you choose — different questions on every generation.</p>
          </div>
        </div>

      </main>
    </div>
  );
}
