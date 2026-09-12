"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Lock, LogIn, User } from "lucide-react";

function LoginForm() {
  const searchParams = useSearchParams();
  const queryError = searchParams.get("error");

  const displayError =
    queryError === "invalid"
      ? "Invalid ID or password. Please try again."
      : queryError === "bad_request"
        ? "Could not process login. Please try again."
        : "";

  return (
    <div className="w-full max-w-md p-8 glass-card rounded-2xl">
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-14 h-14 mb-4 rounded-xl bg-blue-500/20 text-blue-400">
          <Lock className="w-7 h-7" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight">Login</h1>
        <p className="mt-2 text-sm text-gray-400">Enter your ID and password to sign in</p>
      </div>

      {/* Server POST — works without JS (ngrok, password managers, Enter key). */}
      <form action="/api/login" method="post" className="space-y-5">
        <div>
          <label htmlFor="login-id" className="block mb-2 text-sm font-medium text-gray-300">
            ID
          </label>
          <div className="relative">
            <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500" />
            <input
              id="login-id"
              name="id"
              type="text"
              placeholder="Enter your ID"
              required
              autoComplete="username"
              suppressHydrationWarning
              className="w-full py-3 pl-11 pr-4 text-white bg-white/5 border border-white/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 placeholder:text-gray-600"
            />
          </div>
        </div>

        <div>
          <label htmlFor="login-password" className="block mb-2 text-sm font-medium text-gray-300">
            Password
          </label>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500" />
            <input
              id="login-password"
              name="password"
              type="password"
              placeholder="Enter your password"
              required
              autoComplete="current-password"
              suppressHydrationWarning
              className="w-full py-3 pl-11 pr-4 text-white bg-white/5 border border-white/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 placeholder:text-gray-600"
            />
          </div>
        </div>

        {displayError && (
          <p className="text-sm text-red-400 text-center" role="alert">
            {displayError}
          </p>
        )}

        <button
          type="submit"
          className="w-full inline-flex items-center justify-center gap-2 px-6 py-3 text-base font-semibold text-white transition-all duration-200 bg-blue-600 border border-transparent rounded-xl hover:bg-blue-700 shadow-[0_0_20px_rgba(37,99,235,0.4)]"
        >
          <LogIn className="w-5 h-5" />
          Login
        </button>
      </form>
    </div>
  );
}

export default function LoginPage() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-background">
      <div className="absolute top-0 -left-4 w-72 h-72 bg-blue-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob" />
      <div className="absolute top-0 -right-4 w-72 h-72 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000" />

      <main className="relative z-10 flex flex-col items-center justify-center min-h-screen px-4">
        <Suspense fallback={<div className="text-gray-400">Loading…</div>}>
          <LoginForm />
        </Suspense>
      </main>
    </div>
  );
}
