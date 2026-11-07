/**
 * Forgot password page.
 */
import { useState, FormEvent } from 'react';
import { Link } from 'react-router-dom';
import AuthLayout from '../layouts/AuthLayout';
import authService from '../services/authService';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [emailConfigured, setEmailConfigured] = useState(true);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      const response = await authService.forgotPassword(email);
      setSent(true);
      setEmailConfigured(Boolean(response.email_configured));
      setMessage(response.message || 'If an account exists, instructions have been prepared.');
    } catch (err: any) {
      setError(err?.detail || err?.message || 'Something went wrong. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthLayout title="Forgot Password" subtitle="Enter your email to receive a reset link">
      {sent ? (
        <div className="text-center space-y-4">
          {!emailConfigured ? (
            <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-3 rounded-lg text-sm text-left">
              <p className="font-medium mb-1">⚠️ Email Service Not Configured</p>
              <p>{message}</p>
              <p className="mt-2 text-xs text-yellow-700">
                In production, a password reset email would be sent to your address.
                Please configure SMTP or SendGrid provider credentials in backend environment settings.
              </p>
            </div>
          ) : (
            <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg text-sm text-left">
              <p className="font-medium mb-1">✓ Reset Instructions Prepared</p>
              <p>{message}</p>
            </div>
          )}
          <div>
            <Link to="/login" className="inline-block mt-2 text-orange-600 font-medium hover:text-orange-700">
              Back to Login
            </Link>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-5">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
              {error}
            </div>
          )}
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
              Email Address
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 transition"
              placeholder="you@example.com"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full bg-orange-600 text-white py-2.5 px-4 rounded-lg font-medium hover:bg-orange-700 focus:ring-4 focus:ring-orange-200 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? 'Sending...' : 'Send Reset Link'}
          </button>

          <p className="text-center text-sm text-gray-600">
            <Link to="/login" className="text-orange-600 font-medium hover:text-orange-700">
              Back to Login
            </Link>
          </p>
        </form>
      )}
    </AuthLayout>
  );
}
