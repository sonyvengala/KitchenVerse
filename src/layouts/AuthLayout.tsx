/**
 * Auth layout - shared layout for authentication pages.
 */
import { ReactNode } from 'react';
import { Link } from 'react-router-dom';

interface AuthLayoutProps {
  children: ReactNode;
  title: string;
  subtitle?: string;
}

export default function AuthLayout({ children, title, subtitle }: AuthLayoutProps) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-orange-50 to-amber-50 px-4 py-12">
      <div className="max-w-md w-full">
        {/* Logo/Header */}
        <div className="text-center mb-8">
          <Link to="/" className="inline-flex flex-col items-center gap-1 group">
            <div className="flex items-center gap-2.5">
              <div className="w-10 h-10 bg-[#166534] rounded-xl flex items-center justify-center shadow-md group-hover:scale-105 transition-transform">
                <svg className="w-6 h-6 text-amber-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                </svg>
              </div>
              <span className="text-2xl font-black text-gray-900 tracking-tight">
                Kitchen<span className="text-[#F97316]">Verse</span>
              </span>
            </div>
            <span className="text-xs font-semibold text-gray-500 tracking-tight">
              Multiple Kitchens. One Destination.
            </span>
          </Link>
        </div>

        {/* Card */}
        <div className="bg-white rounded-xl shadow-lg p-8">
          <h1 className="text-2xl font-bold text-gray-800 text-center mb-2">{title}</h1>
          {subtitle && <p className="text-gray-500 text-center mb-6">{subtitle}</p>}
          
          {children}
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-gray-500 mt-6 font-medium">
          © 2026 KitchenVerse. All rights reserved.
        </p>
      </div>
    </div>
  );
}
