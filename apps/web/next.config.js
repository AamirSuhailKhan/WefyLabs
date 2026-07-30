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
    const backendUrl = process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';
    const cleanBackendUrl = backendUrl.replace(/\/$/, '');
    return [
      {
        source: '/api/v1/:path*',
        destination: `${cleanBackendUrl}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
