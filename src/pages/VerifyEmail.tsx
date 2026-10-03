/**
 * Email verification page.
 */
import { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import AuthLayout from '../layouts/AuthLayout';
import authService from '../services/authService';

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('');

  useEffect(() => {
    const token = searchParams.get('token');
    if (!token) {
      setStatus('error');
      setMessage('No verification token provided.');
      return;
    }

    const verify = async () => {
      try {
        const response = await authService.verifyEmail(token);
        setStatus('success');
        setMessage(response.message);
      } catch (err: any) {
        setStatus('error');
        setMessage(err.detail || 'Verification failed. The link may have expired.');
      }
    };

    verify();
  }, [searchParams]);

  return (
    <AuthLayout title="Email Verification" subtitle="Verifying your email address...">
      <div className="text-center py-4">
        {status === 'loading' && (
          <div className="space-y-4">
            <svg className="animate-spin h-12 w-12 text-orange-600 mx-auto" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <p className="text-gray-600">Verifying your email...</p>
          </div>
        )}

        {status === 'success' && (
          <div className="space-y-4">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto">
              <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <p className="text-green-700 font-medium">{message}</p>
            <Link
              to="/login"
              className="inline-block bg-orange-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-orange-700 transition"
            >
              Go to Login
            </Link>
          </div>
        )}

        {status === 'error' && (
          <div className="space-y-4">
            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto">
              <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <p className="text-red-700">{message}</p>
            <Link to="/login" className="text-orange-600 font-medium hover:text-orange-700">
              Back to Login
            </Link>
          </div>
        )}
      </div>
    </AuthLayout>
  );
}
