/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  compress: true,
  poweredByHeader: false,
  images: {
    formats: ['image/avif', 'image/webp'],
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**',
      },
    ],
  },
  experimental: {
    optimizePackageImports: ['lucide-react', 'framer-motion', 'recharts'],
  },
  async rewrites() {
    const rawBackendUrl = process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
    let cleanBackendUrl = rawBackendUrl.replace(/\/$/, '');
    if (!cleanBackendUrl.endsWith('/api/v1')) {
      cleanBackendUrl = `${cleanBackendUrl}/api/v1`;
    }
    return [
      {
        source: '/api/v1/:path*',
        destination: `${cleanBackendUrl}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
