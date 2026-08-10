import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

// `output: "export"` (needed so FastAPI can serve the built static files)
// disallows rewrites, so dev mode proxies /api/* to a local backend instead.
export default function nextConfig(phase: string): NextConfig {
  if (phase === PHASE_DEVELOPMENT_SERVER) {
    return {
      async rewrites() {
        return [
          {
            source: "/api/:path*",
            destination: "http://127.0.0.1:8000/api/:path*",
          },
        ];
      },
    };
  }

  return {
    output: "export",
  };
}
