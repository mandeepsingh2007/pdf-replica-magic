"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Lock, LogIn, User } from "lucide-react";

const inputStyle = {
  color: "#0f172a",
  WebkitTextFillColor: "#0f172a",
  caretColor: "#0f172a",
  backgroundColor: "#ffffff",
} as const;

function HindiLoginForm() {
  const searchParams = useSearchParams();
  const queryError = searchParams.get("error");
  const next = searchParams.get("next") ?? "";
  const forEbooks = next.startsWith("/hindi/ebooks");
  const displayError =
    queryError === "invalid"
      ? "गलत आईडी या पासवर्ड। फिर से कोशिश करें।"
      : queryError === "bad_request"
        ? "लॉगिन पूरा नहीं हो सका।"
        : "";

  return (
    <div className="w-full max-w-md p-8 bg-white border-4 border-slate-900 rounded-3xl shadow-[8px_10px_0_#2B2D42] text-slate-900">
      <div className="mb-8 text-center">
        <div className="inline-flex items-center justify-center w-14 h-14 mb-4 text-2xl bg-rose-400 border-2 border-slate-900 rounded-2xl">
          📚
        </div>
        <h1 className="text-2xl font-black text-slate-900">हिंदी पाठमाला लॉगिन</h1>
        <p className="mt-2 text-sm font-semibold text-slate-600">
          {forEbooks
            ? "E-Book पढ़ने के लिए अपनी आईडी और पासवर्ड डालें"
            : "Test Generator के लिए अपनी आईडी और पासवर्ड डालें"}
        </p>
      </div>

      {/* Extensions may add fdprocessedid to form controls before hydration. */}
      <form action="/api/hindi-login" method="post" className="space-y-5">
        {next.startsWith("/hindi/") && <input type="hidden" name="next" value={next} />}
        <div>
          <label htmlFor="hindi-id" className="block mb-2 text-sm font-bold text-slate-800">
            ID
          </label>
          <div className="relative">
            <User className="absolute w-5 h-5 -translate-y-1/2 left-3 top-1/2 text-slate-400" />
            <input
              id="hindi-id"
              name="id"
              type="text"
              required
              autoComplete="username"
              suppressHydrationWarning
              className="hindi-login-input w-full py-3 pl-11 pr-4 font-semibold border-2 border-slate-900 rounded-xl focus:outline-none focus:ring-2 focus:ring-rose-400"
              style={inputStyle}
            />
          </div>
        </div>
        <div>
          <label htmlFor="hindi-password" className="block mb-2 text-sm font-bold text-slate-800">
            Password
          </label>
          <div className="relative">
            <Lock className="absolute w-5 h-5 -translate-y-1/2 left-3 top-1/2 text-slate-400" />
            <input
              id="hindi-password"
              name="password"
              type="password"
              required
              autoComplete="current-password"
              suppressHydrationWarning
              className="hindi-login-input w-full py-3 pl-11 pr-4 font-semibold border-2 border-slate-900 rounded-xl focus:outline-none focus:ring-2 focus:ring-rose-400"
              style={inputStyle}
            />
          </div>
        </div>
        {displayError && (
          <p className="text-sm font-bold text-center text-red-600" role="alert">
            {displayError}
          </p>
        )}
        <button
          type="submit"
          suppressHydrationWarning
          className="inline-flex items-center justify-center w-full gap-2 px-6 py-3 text-base font-black text-white bg-rose-500 border-2 border-slate-900 rounded-xl shadow-[4px_4px_0_#2B2D42]"
        >
          <LogIn className="w-5 h-5" />
          Login
        </button>
      </form>
      <p className="mt-4 text-center">
        <Link href="/hindi" className="text-sm font-bold text-slate-600 underline">
          वापस पोर्टल पर
        </Link>
      </p>
    </div>
  );
}

export default function HindiLoginPage() {
  return (
    <div className="flex items-center justify-center min-h-screen px-4 bg-amber-50 text-slate-900">
      <Suspense fallback={<div className="text-slate-500">Loading…</div>}>
        <HindiLoginForm />
      </Suspense>
    </div>
  );
}
