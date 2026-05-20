import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Enable standalone output for Docker production builds
  output: "standalone",

  // Proxy API requests to the backend during development. The source
  // pattern matches `/api/v1/*` (not `/api/*`) because NEXT_PUBLIC_API_URL
  // already includes the `/api/v1` prefix — matching `/api/*` would double
  // it (e.g. `/api/v1/auth/login` → `${API_URL}/v1/auth/login`).
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
