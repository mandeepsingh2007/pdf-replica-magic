import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow HMR when opening the dev app via ngrok (reduces console WebSocket noise).
  allowedDevOrigins: ["*.ngrok-free.app", "*.ngrok.app"],
};

export default nextConfig;
