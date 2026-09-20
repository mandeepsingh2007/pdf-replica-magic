import type { NextConfig } from "next";

const backend =
  process.env.BACKEND_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Allow HMR when opening the dev app via ngrok (reduces console WebSocket noise).
  allowedDevOrigins: ["*.ngrok-free.app", "*.ngrok.app"],
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${backend}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
