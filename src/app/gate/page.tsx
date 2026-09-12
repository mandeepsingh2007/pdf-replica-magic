"use client";

import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { ScanLine, Smartphone, Loader2 } from "lucide-react";

export default function GatePage() {
  const [loginUrl, setLoginUrl] = useState<string | null>(null);

  useEffect(() => {
    setLoginUrl(`${window.location.origin}/login`);
  }, []);

  return (
    <div className="relative min-h-screen overflow-hidden bg-background">
      <div className="absolute top-0 -left-4 w-72 h-72 bg-blue-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob" />
      <div className="absolute top-0 -right-4 w-72 h-72 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000" />

      <main className="relative z-10 flex flex-col items-center justify-center min-h-screen px-4">
        <div className="w-full max-w-md p-8 glass-card rounded-2xl text-center">
          <div className="inline-flex items-center justify-center w-14 h-14 mb-4 rounded-xl bg-blue-500/20 text-blue-400">
            <ScanLine className="w-7 h-7" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight">Scan to Login</h1>
          <p className="mt-2 mb-8 text-sm text-gray-400">
            Scan the QR code below to open the login page
          </p>

          <div className="inline-flex items-center justify-center p-4 bg-white rounded-2xl mb-6 min-h-[252px] min-w-[252px]">
            {loginUrl ? (
              <QRCodeSVG
                value={loginUrl}
                size={220}
                level="M"
                bgColor="#ffffff"
                fgColor="#09090b"
              />
            ) : (
              <Loader2 className="w-8 h-8 text-gray-400 animate-spin" />
            )}
          </div>

          <div className="flex items-center gap-3 p-3 rounded-xl bg-white/5 border border-white/10">
            <Smartphone className="w-5 h-5 text-blue-400 shrink-0" />
            <p className="text-xs text-gray-400 text-left">
              Open your camera app and point it at the QR code to get started
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
