/** @type {import('next').NextConfig} */
const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
const nextConfig = {
  reactStrictMode: true,
  // Proxy /api/* to the FastAPI backend so the browser only needs port 3000
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};
export default nextConfig;
