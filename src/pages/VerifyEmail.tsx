/**
 * Email verification page.
 */
import { useState, useEffect, useRef } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import AuthLayout from '../layouts/AuthLayout';
import authService from '../services/authService';
import { useAuth } from '../hooks/useAuth';
import { CheckCircle2, AlertTriangle, XCircle, ArrowRight, RefreshCw, Mail } from 'lucide-react';

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { fetchUser, user, isAuthenticated } = useAuth();

  const [status, setStatus] = useState<
    'loading' | 'success' | 'expired' | 'invalid' | 'already_used' | 'pending_token'
  >('loading');
  const [message, setMessage] = useState('');
  const [resendStatus, setResendStatus] = useState('');
  const [resending, setResending] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  // Guard against React 18 StrictMode double-fetch consuming the single-use token
  const hasAttemptedRef = useRef(false);

  useEffect(() => {
    let timer: any;
    if (cooldown > 0) {
      timer = setTimeout(() => setCooldown((c) => c - 1), 1000);
    }
    return () => clearTimeout(timer);
  }, [cooldown]);

  useEffect(() => {
    const token = searchParams.get('token');

    // Case A: User arrived on /verify-email directly without a token (e.g. from banner or link)
    if (!token) {
      if (user?.is_verified || user?.is_email_verified) {
        setStatus('success');
        setMessage('Your email is already verified.');
      } else {
        setStatus('pending_token');
        setMessage(
          user?.email
            ? `Verification email sent to ${user.email}`
            : 'Please check your email inbox for the verification link.'
        );
      }
      return;
    }

    // Case B: User clicked a link with a token (?token=...)
    if (hasAttemptedRef.current) return;
    hasAttemptedRef.current = true;

    const verify = async () => {
      try {
        const response = await authService.verifyEmail(token);
        setStatus('success');
        setMessage(response.message || 'Email verified successfully.');
        // Refresh authenticated user state immediately
        try {
          await fetchUser();
        } catch {
          // ignore
        }
      } catch (err: any) {
        const detail = (err?.detail || err?.message || '').toLowerCase();
        if (detail.includes('expired')) {
          setStatus('expired');
          setMessage('Verification link expired.');
        } else if (
          detail.includes('already used') ||
          detail.includes('already verified') ||
          detail.includes('already been used')
        ) {
          setStatus('already_used');
          setMessage(err?.detail || 'This verification link has already been used.');
          // Refresh user in case they are already verified
          try {
            await fetchUser();
          } catch {
            // ignore
          }
        } else {
          setStatus('invalid');
          setMessage(err?.detail || 'Verification link is invalid.');
        }
      }
    };

    verify();
  }, [searchParams, fetchUser, user]);

  const handleResend = async () => {
    if (cooldown > 0 || resending) return;
    setResending(true);
    setResendStatus('');
    try {
      const emailToUse = user?.email;
      const res = await authService.resendVerification(emailToUse);
      setResendStatus(`Verification link sent! ${res.message || ''}`);
      setCooldown(res.cooldown_seconds || 60);
    } catch (err: any) {
      setResendStatus(err?.detail || 'Failed to resend verification email.');
    } finally {
      setResending(false);
    }
  };

  return (
    <AuthLayout title="Email Verification" subtitle="Securing your KitchenVerse account...">
      <div className="text-center py-6 space-y-6">
        {status === 'loading' && (
          <div className="space-y-4">
            <div className="w-14 h-14 border-4 border-amber-600/30 border-t-amber-600 rounded-full animate-spin mx-auto" />
            <p className="text-sm font-semibold text-gray-600">Verifying your security token...</p>
          </div>
        )}

        {status === 'success' && (
          <div className="space-y-5 animate-in fade-in duration-200">
            <div className="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-3xl flex items-center justify-center mx-auto shadow-xs">
              <CheckCircle2 className="w-10 h-10" />
            </div>
            <div className="space-y-1">
              <h3 className="text-xl font-black text-gray-900">Email verified successfully.</h3>
              <p className="text-xs text-gray-500">
                Your account is fully verified. You can now checkout and track live orders!
              </p>
            </div>
            <div className="pt-2">
              <button
                onClick={() => navigate('/')}
                className="w-full bg-[#166534] hover:bg-[#15803d] text-white py-3 rounded-xl font-bold text-sm transition-all shadow-md flex items-center justify-center gap-2"
              >
                Continue to Customer Portal <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {status === 'pending_token' && (
          <div className="space-y-5 animate-in fade-in duration-200">
            <div className="w-16 h-16 bg-amber-100 text-amber-600 rounded-3xl flex items-center justify-center mx-auto shadow-xs">
              <Mail className="w-10 h-10" />
            </div>
            <div className="space-y-1">
              <h3 className="text-xl font-black text-gray-900">Verify your email to unlock all features.</h3>
              <p className="text-xs text-gray-600 leading-relaxed max-w-sm mx-auto">
                {user?.email ? (
                  <>
                    Verification email sent to <strong className="text-gray-900">{user.email}</strong>. Please
                    click the link in that email to activate your account.
                  </>
                ) : (
                  'Please open the verification link sent to your email address.'
                )}
              </p>
            </div>

            {resendStatus && (
              <p className="text-xs font-semibold text-emerald-700 bg-emerald-50 py-2 px-3 rounded-xl border border-emerald-200">
                {resendStatus}
              </p>
            )}

            <div className="pt-2 space-y-3">
              {isAuthenticated && (
                <button
                  onClick={handleResend}
                  disabled={resending || cooldown > 0}
                  className="w-full bg-orange-600 hover:bg-orange-700 disabled:opacity-50 text-white py-3 rounded-xl font-bold text-sm transition-all shadow-md flex items-center justify-center gap-2"
                >
                  <RefreshCw className={`w-4 h-4 ${resending ? 'animate-spin' : ''}`} />
                  {cooldown > 0 ? `Resend Available in ${cooldown}s` : 'Resend Verification Email'}
                </button>
              )}
              <Link
                to="/"
                className="inline-block text-xs font-bold text-gray-500 hover:text-gray-800"
              >
                Return to Customer Portal
              </Link>
            </div>
          </div>
        )}

        {status === 'already_used' && (
          <div className="space-y-5 animate-in fade-in duration-200">
            <div className="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-3xl flex items-center justify-center mx-auto shadow-xs">
              <CheckCircle2 className="w-10 h-10" />
            </div>
            <div className="space-y-1">
              <h3 className="text-xl font-black text-gray-900">Verification link already used.</h3>
              <p className="text-xs text-gray-500">
                This verification link was already activated. Your email is verified and ready to use!
              </p>
            </div>
            <div className="pt-2">
              <button
                onClick={() => navigate('/')}
                className="w-full bg-[#166534] hover:bg-[#15803d] text-white py-3 rounded-xl font-bold text-sm transition-all shadow-md flex items-center justify-center gap-2"
              >
                Continue to Customer Portal <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {status === 'expired' && (
          <div className="space-y-5 animate-in fade-in duration-200">
            <div className="w-16 h-16 bg-amber-100 text-amber-600 rounded-3xl flex items-center justify-center mx-auto shadow-xs">
              <AlertTriangle className="w-10 h-10" />
            </div>
            <div className="space-y-1">
              <h3 className="text-xl font-black text-gray-900">Verification link expired.</h3>
              <p className="text-xs text-gray-500">
                Security tokens expire after 24 hours. Request a fresh verification link below.
              </p>
            </div>

            {resendStatus && (
              <p className="text-xs font-semibold text-emerald-700 bg-emerald-50 py-2 px-3 rounded-xl border border-emerald-200">
                {resendStatus}
              </p>
            )}

            <div className="pt-2 space-y-3">
              <button
                onClick={handleResend}
                disabled={resending || cooldown > 0}
                className="w-full bg-orange-600 hover:bg-orange-700 disabled:opacity-50 text-white py-3 rounded-xl font-bold text-sm transition-all shadow-md flex items-center justify-center gap-2"
              >
                <RefreshCw className={`w-4 h-4 ${resending ? 'animate-spin' : ''}`} />
                {cooldown > 0 ? `Resend Available in ${cooldown}s` : 'Resend Verification Email'}
              </button>
              <Link
                to="/"
                className="inline-block text-xs font-bold text-gray-500 hover:text-gray-800"
              >
                Return to Customer Portal
              </Link>
            </div>
          </div>
        )}

        {status === 'invalid' && (
          <div className="space-y-5 animate-in fade-in duration-200">
            <div className="w-16 h-16 bg-red-100 text-red-600 rounded-3xl flex items-center justify-center mx-auto shadow-xs">
              <XCircle className="w-10 h-10" />
            </div>
            <div className="space-y-1">
              <h3 className="text-xl font-black text-gray-900">Verification link is invalid.</h3>
              <p className="text-xs text-gray-500">
                This link is broken or has already been used. Please request a new verification email.
              </p>
            </div>

            {resendStatus && (
              <p className="text-xs font-semibold text-emerald-700 bg-emerald-50 py-2 px-3 rounded-xl border border-emerald-200">
                {resendStatus}
              </p>
            )}

            <div className="pt-2 space-y-3">
              {isAuthenticated && (
                <button
                  onClick={handleResend}
                  disabled={resending || cooldown > 0}
                  className="w-full bg-orange-600 hover:bg-orange-700 disabled:opacity-50 text-white py-3 rounded-xl font-bold text-sm transition-all shadow-md flex items-center justify-center gap-2"
                >
                  <RefreshCw className={`w-4 h-4 ${resending ? 'animate-spin' : ''}`} />
                  {cooldown > 0 ? `Resend in ${cooldown}s` : 'Resend Verification Email'}
                </button>
              )}
              <Link
                to="/login"
                className="inline-block text-xs font-bold text-gray-600 hover:text-gray-900"
              >
                Go to Login
              </Link>
            </div>
          </div>
        )}
      </div>
    </AuthLayout>
  );
}
