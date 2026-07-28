'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { ArrowRight, Menu, X } from 'lucide-react';

import { BeetleLabsLogo } from './BeetleLabsLogo';

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <div className="fixed top-0 left-0 right-0 z-50">
      {/* Announcement Banner */}
      <div className="bg-[#1A1A1A] text-white text-xs font-medium py-2 px-4 flex items-center justify-center gap-3">
        <span>A letter to our users, customers and friends</span>
        <button onClick={() => window.location.href = '#how-it-works'} className="bg-white text-[#1A1A1A] text-xs font-semibold px-3 py-1 rounded-full hover:bg-[#E8F5A8] transition-colors">
          Read more →
        </button>
      </div>

      {/* Main Nav */}
      <nav
        className={`h-16 px-6 flex items-center justify-between transition-all duration-300 ${
          scrolled
            ? 'bg-[rgba(240,237,232,0.85)] backdrop-blur-md border-b border-[#D4D0C8]'
            : 'bg-transparent'
        }`}
      >
        {/* Logo */}
        <BeetleLabsLogo href="/" iconSize={26} textSize="text-xl" />

        {/* Desktop Nav Links */}
        <div className="hidden md:flex items-center gap-8">
          <Link href="#features" className="text-sm font-medium text-[#4A4A4A] hover:text-[#1A1A1A] transition-colors">
            Features
          </Link>
          <Link href="#how-it-works" className="text-sm font-medium text-[#4A4A4A] hover:text-[#1A1A1A] transition-colors">
            How it works
          </Link>
          <Link href="#pricing" className="text-sm font-medium text-[#4A4A4A] hover:text-[#1A1A1A] transition-colors">
            Pricing
          </Link>
        </div>

        {/* Desktop CTAs */}
        <div className="hidden md:flex items-center gap-3">
          <Link
            href="/login"
            className="btn-outline text-[11px]"
          >
            LOG IN
          </Link>
          <Link
            href="/register"
            className="btn-lime text-[11px] flex items-center gap-1.5"
          >
            START TESTING
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {/* Mobile Toggle */}
        <button
          className="md:hidden text-[#1A1A1A] p-2"
          onClick={() => setMobileOpen(!mobileOpen)}
        >
          {mobileOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
      </nav>

      {/* Mobile Menu */}
      {mobileOpen && (
        <div className="md:hidden bg-[#FAF7F2] border-b border-[#D4D0C8] p-5 space-y-4 shadow-sm">
          <Link href="#features" onClick={() => setMobileOpen(false)} className="block text-sm text-[#4A4A4A] hover:text-[#1A1A1A]">Features</Link>
          <Link href="#how-it-works" onClick={() => setMobileOpen(false)} className="block text-sm text-[#4A4A4A] hover:text-[#1A1A1A]">How it works</Link>
          <Link href="#pricing" onClick={() => setMobileOpen(false)} className="block text-sm text-[#4A4A4A] hover:text-[#1A1A1A]">Pricing</Link>
          <div className="flex flex-col gap-3 pt-2 border-t border-[#D4D0C8]">
            <Link href="/login" className="btn-outline w-full justify-center">LOG IN</Link>
            <Link href="/register" className="btn-lime w-full justify-center">START TESTING →</Link>
          </div>
        </div>
      )}
    </div>
  );
}
