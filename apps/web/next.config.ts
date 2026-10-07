import type { NextConfig } from "next";
const apiOrigin = process.env.API_ORIGIN;
if (process.env.NODE_ENV === 'production' && !apiOrigin) {
  throw new Error('API_ORIGIN must be explicitly configured for production build/start');
}
if (apiOrigin) {
  const parsed = new URL(apiOrigin);
  if (process.env.CREDITIQ_DEPLOYMENT === 'true' && (parsed.protocol !== 'https:'
      || ['localhost', '127.0.0.1', '[::1]'].includes(parsed.hostname) || parsed.hostname.includes('<'))) {
    throw new Error('Deployed API_ORIGIN must use a public HTTPS endpoint');
  }
  if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password
      || parsed.search || parsed.hash || parsed.pathname !== '/') {
    throw new Error('API_ORIGIN must be an HTTP(S) origin without credentials or paths');
  }
}
const config: NextConfig = {
  distDir: process.env.CREDITIQ_WEB_DIST_DIR || '.next',
  async rewrites() { return [{ source: "/api/:path*", destination: `${(apiOrigin || "http://127.0.0.1:8000").replace(/\/$/, '')}/api/:path*` }]; }
};
export default config;

