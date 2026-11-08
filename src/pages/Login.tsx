/**
 * Login page.
 */
import { useState, FormEvent } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { getValidDestinationForRole } from '../utils/roleUtils';
import AuthLayout from '../layouts/AuthLayout';

/** Map API error messages / HTTP status codes to user-friendly text. */
function getLoginErrorMessage(err: any): string {
  const status: number = err?.status ?? 0;
  const detail: string = (err?.detail || err?.message || '').toLowerCase();

  // Network / backend offline
  if (status === 0 || status === 502 || status === 503 || status === 504) {
    return 'Cannot connect to server. Please ensure the backend is running and try again.';
  }
  if (status === 404) {
    return 'Authentication service endpoint not found (404). Please ensure the backend server is running and API URL is configured correctly.';
  }
  if (status >= 500) {
    return 'Server error. Please try again in a moment.';
  }

  // 401 - bad credentials
  if (status === 401) {
    return 'Invalid email or password. Please check your credentials and try again.';
  }

  // 403 - account state issues
  if (status === 403) {
    if (detail.includes('deactivated') || detail.includes('inactive')) {
      return 'Your account has been deactivated. Please contact support.';
    }
    if (detail.includes('suspended')) {
      return 'Your account has been suspended. Please contact support.';
    }
    if (detail.includes('pending') || detail.includes('approval')) {
      return 'Your account is pending admin approval. You will be notified once reviewed.';
    }
    if (detail.includes('verif') || detail.includes('email')) {
      return 'Please verify your email address before logging in. Check your inbox for the verification link.';
    }
    return err?.detail || 'Access denied. Please contact support.';
  }

  // 422 - validation error (e.g. bad email format)
  if (status === 422) {
    return 'Please enter a valid email address and password.';
  }

  // Return server-provided message as a fallback (it's already safe from our backend)
  if (err?.detail && typeof err.detail === 'string' && err.detail.length < 200) {
    return err.detail;
  }

  return 'Login failed. Please try again.';
}

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login, clearError } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    clearError();
    setIsLoading(true);

    try {
      const loggedUser = await login(email, password);
      const targetFrom = (location.state as any)?.from?.pathname;
      const destination = getValidDestinationForRole(targetFrom, loggedUser.role);
      navigate(destination, { replace: true });
    } catch (err: any) {
      setError(getLoginErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthLayout title="Welcome Back" subtitle="Sign in to your account">
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

        <div>
          <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
            Password
          </label>
          <input
            id="password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 transition"
            placeholder="••••••••"
          />
        </div>

        <div className="flex items-center justify-end">
          <Link to="/forgot-password" className="text-sm text-orange-600 hover:text-orange-700">
            Forgot password?
          </Link>
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="w-full bg-orange-600 text-white py-2.5 px-4 rounded-lg font-medium hover:bg-orange-700 focus:ring-4 focus:ring-orange-200 transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Signing in...
            </span>
          ) : (
            'Sign In'
          )}
        </button>
      </form>

      <p className="text-center text-sm text-gray-600 mt-6">
        Don't have an account?{' '}
        <Link to="/register" className="text-orange-600 font-medium hover:text-orange-700">
          Create one
        </Link>
      </p>
    </AuthLayout>
  );
}
