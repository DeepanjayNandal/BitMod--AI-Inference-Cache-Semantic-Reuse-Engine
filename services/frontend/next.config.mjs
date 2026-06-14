/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  typescript: { ignoreBuildErrors: false },
  images: {
    dangerouslyAllowSVG: true,
    contentDispositionType: 'attachment',
    contentSecurityPolicy: "default-src 'self'; script-src 'none'; sandbox;",
  },
}

export default nextConfig
