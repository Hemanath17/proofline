import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  async rewrites() {
    // Development only: `vercel dev` and production both route /api/*
    // to the FastAPI service via the root vercel.json, which does not
    // apply to `npm --prefix web run dev` running the Next.js app on its
    // own -- this rewrite stands in for that, so the API client's plain
    // relative fetches ("/api/...") work either way.
    if (process.env.NODE_ENV !== "development") {
      return [];
    }
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
