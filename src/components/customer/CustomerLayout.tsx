/**
 * Customer Layout Component
 * Modern food-tech navigation bar, notification bell, real-time cart badge,
 * and user account menu.
 */

import React, { useState, useEffect } from 'react';
import { Link, Outlet, useNavigate, useLocation, Navigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { useCart } from '../../context/CartContext';
import { customerApi } from '../../services/customerApi';
import { normalizeRole } from '../../utils/roleUtils';
import {
  Utensils,
  ShoppingBag,
  Bell,
  User as UserIcon,
  LogOut,
  Clock,
  ChevronDown,
  Menu,
  X,
  Store,
  Compass,
  AlertTriangle,
  Mail,
} from 'lucide-react';
import authService from '../../services/authService';

import { useRealtime } from '../../context/RealtimeContext';

export default function CustomerLayout() {
  const { user, isAuthenticated, isLoading, logout, fetchUser } = useAuth();
  const { itemCount } = useCart();
  const { subscribe } = useRealtime();
  const navigate = useNavigate();
  const location = useLocation();

  const [unreadNotifications, setUnreadNotifications] = useState(0);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [resending, setResending] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const [bannerMsg, setBannerMsg] = useState('');
  const [showVerifyModal, setShowVerifyModal] = useState(false);

  useEffect(() => {
    let timer: any;
    if (resendCooldown > 0) {
      timer = setTimeout(() => setResendCooldown((c) => c - 1), 1000);
    }
    return () => clearTimeout(timer);
  }, [resendCooldown]);

  const fetchNotifs = () => {
    if (isAuthenticated && !isLoading) {
      customerApi.getNotifications()
        .then((notifs) => {
          const unread = notifs.filter((n) => !n.is_read).length;
          setUnreadNotifications(unread);
        })
        .catch(() => {});
    }
  };

  useEffect(() => {
    fetchNotifs();

    const unsubNotif = subscribe('NOTIFICATION_NEW', fetchNotifs);
    const unsubOrder = subscribe('ORDER_STATUS_CHANGED', fetchNotifs);

    return () => {
      unsubNotif();
      unsubOrder();
    };
  }, [isAuthenticated, isLoading, location.pathname, subscribe]);

  const handleResendEmail = async () => {
    if (resendCooldown > 0 || resending) return;
    setResending(true);
    setBannerMsg('');
    try {
      const res = await authService.resendVerification(user?.email);
      setBannerMsg(res.message || 'Verification email resent!');
      setResendCooldown(res.cooldown_seconds || 60);
    } catch (err: any) {
      setBannerMsg(err?.detail || 'Failed to send verification email');
    } finally {
      setResending(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    setUserDropdownOpen(false);
    navigate('/login');
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FFFDF8]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#166534] to-[#15803d] flex items-center justify-center text-white shadow-xs animate-pulse">
            <span className="text-lg font-black text-amber-300">KV</span>
          </div>
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-600 mt-2"></div>
          <span className="text-sm font-semibold text-gray-600">Loading KitchenVerse...</span>
        </div>
      </div>
    );
  }

  // Authoritative role routing: non-customer authenticated roles must never render Customer Portal
  if (isAuthenticated && user) {
    const role = normalizeRole(user.role);
    if (role === 'KITCHEN_OWNER') {
      return <Navigate to="/kitchen/dashboard" replace />;
    }
    if (role === 'ADMIN') {
      return <Navigate to="/admin/dashboard" replace />;
    }
  }

  const navLinks = [
    { name: 'Explore', path: '/', icon: Compass },
    { name: 'Kitchens', path: '/kitchens', icon: Store },
    { name: 'Menu', path: '/menu', icon: Utensils },
    ...(isAuthenticated ? [{ name: 'My Orders', path: '/orders', icon: Clock }] : []),
  ];

  const isActive = (path: string) => {
    if (path === '/' && location.pathname === '/') return true;
    if (path !== '/' && location.pathname.startsWith(path)) return true;
    return false;
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#FFFDF8] text-[#172033]">
      {/* Top Header */}
      <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-md border-b border-amber-900/10 shadow-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16 gap-4">
            {/* Logo */}
            <Link to="/" className="flex items-center gap-2.5 shrink-0 group">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#166534] to-[#15803d] flex items-center justify-center text-white shadow-xs group-hover:scale-105 transition-transform">
                <Utensils className="w-5 h-5 text-amber-300" />
              </div>
              <div className="flex flex-col">
                <span className="text-lg font-black tracking-tight text-[#172033] leading-none">
                  Kitchen<span className="text-[#F97316]">Verse</span>
                </span>
                <span className="text-[10px] text-gray-500 font-semibold tracking-tight mt-0.5">
                  Multiple Kitchens. One Destination.
                </span>
              </div>
            </Link>

            {/* Desktop Navigation Links */}
            <nav className="hidden md:flex items-center gap-1">
              {navLinks.map((link) => {
                const Icon = link.icon;
                const active = isActive(link.path);
                return (
                  <Link
                    key={link.path}
                    to={link.path}
                    className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-sm font-semibold transition-all ${
                      active
                        ? 'bg-[#166534]/10 text-[#166534]'
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100/80'
                    }`}
                  >
                    <Icon className={`w-4 h-4 ${active ? 'text-[#166534]' : 'text-gray-400'}`} />
                    <span>{link.name}</span>
                  </Link>
                );
              })}
            </nav>

            {/* Action Buttons */}
            <div className="flex items-center gap-2.5">
              {/* Header Email Not Verified Indicator */}
              {isAuthenticated && user && !user.is_verified && (
                <button
                  type="button"
                  onClick={() => setShowVerifyModal(true)}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-300 text-xs font-bold transition-colors cursor-pointer"
                  title="Email not verified - Click for instructions"
                >
                  <span>⚠ Email not verified</span>
                </button>
              )}

              {/* Notifications */}
              {isAuthenticated && (
                <Link
                  to="/notifications"
                  className="relative p-2.5 rounded-xl text-gray-600 hover:text-gray-900 hover:bg-gray-100/80 transition-colors"
                  title="Notifications"
                >
                  <Bell className="w-5 h-5" />
                  {unreadNotifications > 0 && (
                    <span className="absolute top-1.5 right-1.5 w-4 h-4 bg-[#F97316] text-white text-[10px] font-bold rounded-full flex items-center justify-center animate-pulse">
                      {unreadNotifications > 9 ? '9+' : unreadNotifications}
                    </span>
                  )}
                </Link>
              )}

              {/* Shopping Cart Button */}
              <Link
                to="/cart"
                className="relative flex items-center gap-2 px-3.5 py-2 bg-gradient-to-r from-[#166534] to-[#15803d] hover:from-[#15803d] hover:to-[#166534] text-white rounded-xl text-sm font-bold shadow-xs hover:shadow-md transition-all active:scale-95"
              >
                <ShoppingBag className="w-4 h-4" />
                <span className="hidden sm:inline">Cart</span>
                {itemCount > 0 && (
                  <span className="px-1.5 py-0.5 bg-[#F97316] text-white text-xs font-black rounded-full min-w-5 text-center">
                    {itemCount}
                  </span>
                )}
              </Link>

              {/* User Account / Auth */}
              {isAuthenticated ? (
                <div className="relative">
                  <button
                    onClick={() => setUserDropdownOpen(!userDropdownOpen)}
                    className="flex items-center gap-2 p-1.5 rounded-xl hover:bg-gray-100 transition-colors"
                  >
                    <div className="w-8 h-8 rounded-full bg-emerald-100 border border-emerald-300 flex items-center justify-center text-[#166534] font-bold text-xs">
                      {user?.first_name?.[0] || user?.email?.[0]?.toUpperCase() || 'U'}
                    </div>
                    <ChevronDown className="w-3.5 h-3.5 text-gray-500 hidden sm:block" />
                  </button>

                  {userDropdownOpen && (
                    <div
                      className="absolute right-0 mt-2 w-56 bg-white rounded-2xl shadow-xl border border-gray-100 py-2 z-50 animate-in fade-in slide-in-from-top-2 duration-150"
                      onMouseLeave={() => setUserDropdownOpen(false)}
                    >
                      <div className="px-4 py-3 border-b border-gray-100">
                        <p className="text-sm font-bold text-gray-900 truncate">
                          {`${user?.first_name || ''} ${user?.last_name || ''}`.trim() || 'My Account'}
                        </p>
                        <p className="text-xs text-gray-500 truncate">{user?.email}</p>
                        <span className="inline-block mt-1.5 px-2 py-0.5 bg-emerald-50 text-[#166534] rounded-md text-[10px] font-bold uppercase tracking-wider">
                          {user?.role}
                        </span>
                      </div>


                      <Link
                        to="/profile"
                        onClick={() => setUserDropdownOpen(false)}
                        className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50"
                      >
                        <UserIcon className="w-4 h-4" />
                        <span>Profile & Addresses</span>
                      </Link>

                      <Link
                        to="/orders"
                        onClick={() => setUserDropdownOpen(false)}
                        className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50"
                      >
                        <Clock className="w-4 h-4" />
                        <span>My Orders</span>
                      </Link>

                      <div className="border-t border-gray-100 my-1"></div>

                      <button
                        onClick={handleLogout}
                        className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-rose-600 hover:bg-rose-50 font-medium text-left"
                      >
                        <LogOut className="w-4 h-4" />
                        <span>Sign Out</span>
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Link
                    to="/login"
                    className="px-3.5 py-2 text-sm font-semibold text-gray-700 hover:text-[#166534] transition-colors"
                  >
                    Log In
                  </Link>
                  <Link
                    to="/register"
                    className="px-3.5 py-2 bg-[#F97316] hover:bg-orange-600 text-white rounded-xl text-sm font-bold shadow-2xs transition-colors"
                  >
                    Sign Up
                  </Link>
                </div>
              )}

              {/* Mobile menu button */}
              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="md:hidden p-2 rounded-xl text-gray-600 hover:bg-gray-100"
              >
                {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile menu dropdown */}
        {mobileMenuOpen && (
          <div className="md:hidden bg-white border-b border-gray-200 px-4 py-3 space-y-1">
            {navLinks.map((link) => {
              const Icon = link.icon;
              return (
                <Link
                  key={link.path}
                  to={link.path}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold ${
                    isActive(link.path)
                      ? 'bg-[#166534]/10 text-[#166534]'
                      : 'text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span>{link.name}</span>
                </Link>
              );
            })}
          </div>
        )}
      </header>

      {/* Global Email Verification Banner */}
      {isAuthenticated && user && !user.is_verified && (
        <div className="bg-amber-50/95 border-b border-amber-200 px-4 py-2 text-xs">
          <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2.5">
            <div className="flex items-center gap-2 text-amber-900 font-medium">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
              <span>
                <strong>Verify your email to unlock all KitchenVerse features.</strong>{' '}
                <span className="text-amber-700">Verification email sent to {user.email}</span>
              </span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {bannerMsg && (
                <span className="text-[11px] font-semibold text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded">
                  {bannerMsg}
                </span>
              )}
              <button
                type="button"
                onClick={() => navigate('/verify-email')}
                className="px-3 py-1 bg-[#166534] hover:bg-[#15803d] text-white rounded-lg text-xs font-bold transition shadow-xs"
              >
                Verify Email
              </button>
              <button
                type="button"
                onClick={handleResendEmail}
                disabled={resending || resendCooldown > 0}
                className="px-3 py-1 bg-white hover:bg-amber-100 text-amber-900 border border-amber-300 rounded-lg text-xs font-bold transition disabled:opacity-50"
              >
                {resendCooldown > 0 ? `Resend (${resendCooldown}s)` : 'Resend Verification Email'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Verification Instructions Modal */}
      {showVerifyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-gray-100 space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2 text-amber-900 font-bold text-base">
                <AlertTriangle className="w-5 h-5 text-amber-600" />
                <span>Email Verification Pending</span>
              </div>
              <button
                onClick={() => setShowVerifyModal(false)}
                className="p-1 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-2 text-xs text-gray-600 leading-relaxed">
              <p>
                A verification link was sent to: <strong>{user?.email}</strong>
              </p>
              <p>
                Please check your inbox and click the verification link to unlock order checkout. If you haven't received it, you can request a fresh email below.
              </p>
            </div>

            {bannerMsg && (
              <div className="text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 p-2.5 rounded-xl">
                {bannerMsg}
              </div>
            )}

            <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-gray-100">
              <button
                type="button"
                onClick={handleResendEmail}
                disabled={resending || resendCooldown > 0}
                className="px-3.5 py-2 rounded-xl text-xs font-bold bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-50 transition"
              >
                {resendCooldown > 0 ? `Resend (${resendCooldown}s)` : 'Resend Verification Email'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowVerifyModal(false);
                  navigate('/verify-email');
                }}
                className="px-3.5 py-2 rounded-xl text-xs font-bold bg-[#166534] hover:bg-[#15803d] text-white transition shadow-xs"
              >
                Verify Email
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Page Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-amber-900/10 py-10 mt-16 text-gray-500 text-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-[#166534] flex items-center justify-center text-white shadow-xs">
              <Utensils className="w-4 h-4 text-amber-300" />
            </div>
            <div className="flex flex-col">
              <span className="font-black text-[#172033] leading-none">
                Kitchen<span className="text-[#F97316]">Verse</span>
              </span>
              <span className="text-[10px] text-gray-500 font-medium tracking-tight mt-0.5">
                Multiple Kitchens. One Destination.
              </span>
            </div>
          </div>
          <p>© 2026 KitchenVerse. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
