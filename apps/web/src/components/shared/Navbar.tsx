'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { ArrowRight, Menu, X } from 'lucide-react';

import { BeetleLabsLogo } from './BeetleLabsLogo';
import RegionSwitcher from './RegionSwitcher';

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <header className="fixed top-0 left-0 right-0 z-50 transition-all duration-300">
      {/* Main Navigation Bar */}
      <nav
        className={`h-16 px-4 sm:px-6 flex items-center justify-between transition-all duration-300 ${
          scrolled
            ? 'bg-[rgba(240,237,232,0.92)] backdrop-blur-md border-b border-[#D4D0C8] shadow-xs'
            : 'bg-[#F0EDE8]/90 backdrop-blur-sm border-b border-[#D4D0C8]/60'
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

        {/* Desktop Action Buttons & Region Selector */}
        <div className="hidden md:flex items-center gap-3">
          <RegionSwitcher />
          <Link
            href="/login"
            className="btn-outline text-[11px] py-1.5 px-3 whitespace-nowrap"
          >
            LOG IN
          </Link>
          <Link
            href="/register"
            className="btn-lime text-[11px] py-1.5 px-3.5 flex items-center gap-1.5 whitespace-nowrap"
          >
            START TESTING
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {/* Mobile Menu Toggle Button */}
        <button
          className="md:hidden text-[#1A1A1A] p-2 rounded-lg hover:bg-black/5"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Toggle Navigation Menu"
        >
          {mobileOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
      </nav>

      {/* Mobile Nav Dropdown */}
      {mobileOpen && (
        <div className="md:hidden bg-[#FAF7F2] border-b border-[#D4D0C8] p-5 space-y-4 shadow-md">
          <Link href="#features" onClick={() => setMobileOpen(false)} className="block text-sm font-medium text-[#4A4A4A] hover:text-[#1A1A1A]">Features</Link>
          <Link href="#how-it-works" onClick={() => setMobileOpen(false)} className="block text-sm font-medium text-[#4A4A4A] hover:text-[#1A1A1A]">How it works</Link>
          <Link href="#pricing" onClick={() => setMobileOpen(false)} className="block text-sm font-medium text-[#4A4A4A] hover:text-[#1A1A1A]">Pricing</Link>
          <div className="flex flex-col gap-3 pt-3 border-t border-[#D4D0C8]">
            <div className="flex items-center justify-between pb-1">
              <span className="text-xs text-gray-500 font-medium">Selected Region:</span>
              <RegionSwitcher />
            </div>
            <Link href="/login" className="btn-outline w-full justify-center">LOG IN</Link>
            <Link href="/register" className="btn-lime w-full justify-center">START TESTING →</Link>
          </div>
        </div>
      )}
    </header>
  );
}
