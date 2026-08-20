/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable full Serverless API routes on Vercel. (Optional static export if CF_PAGES=1)
  output: process.env.CF_PAGES === "1" ? "export" : undefined,
  // Image optimisation requires a server runtime — disable so the
  // export contains the original asset bytes.
  images: {
    unoptimized: true,
  },
  // Trailing slashes on every URL so Pages serves matching index.html
  trailingSlash: true,
};

export default nextConfig;
