/**
 * Register page.
 */
import { useState, FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import AuthLayout from '../layouts/AuthLayout';
import { LicenseUploadSection } from '../components/license/LicenseUploadSection';

export default function Register() {
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    first_name: '',
    last_name: '',
    role: 'CUSTOMER' as 'CUSTOMER' | 'KITCHEN_OWNER',
    kitchen_name: '',
    address: '',
    city: '',
    phone_number: '',
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { register, clearError } = useAuth();
  const navigate = useNavigate();

  const [licenseData, setLicenseData] = useState({
    license_number: '',
    business_name: '',
    expiry_date: '',
    document_base64: '',
    filename: '',
  });

  const validatePassword = (password: string): string[] => {
    const errors: string[] = [];
    if (password.length < 8) errors.push('At least 8 characters');
    if (!/[A-Z]/.test(password)) errors.push('One uppercase letter');
    if (!/[a-z]/.test(password)) errors.push('One lowercase letter');
    if (!/[0-9]/.test(password)) errors.push('One digit');
    if (!/[!@#$%^&*()_+\-=\[\]{}|;:',.<>?/~`]/.test(password)) errors.push('One special character');
    return errors;
  };

  const passwordErrors = validatePassword(formData.password);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    clearError();

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (passwordErrors.length > 0) {
      setError(`Password requirements: ${passwordErrors.join(', ')}`);
      return;
    }

    if (formData.role === 'KITCHEN_OWNER') {
      if (!licenseData.license_number || !licenseData.license_number.trim()) {
        setError('FSSAI License registration number is required for kitchen owners.');
        return;
      }
      if (!licenseData.document_base64) {
        setError('FSSAI License document is required for kitchen owners.');
        return;
      }
    }

    setIsLoading(true);

    try {
      const message = await register({
        email: formData.email,
        password: formData.password,
        first_name: formData.first_name,
        last_name: formData.last_name,
        role: formData.role,
        kitchen_name: formData.kitchen_name || undefined,
        address: formData.address || undefined,
        city: formData.city || undefined,
        phone_number: formData.phone_number || undefined,
        fssai_license_number: formData.role === 'KITCHEN_OWNER' ? licenseData.license_number : undefined,
        fssai_business_name: formData.role === 'KITCHEN_OWNER' ? licenseData.business_name : undefined,
        fssai_expiry_date: formData.role === 'KITCHEN_OWNER' ? licenseData.expiry_date : undefined,
        fssai_document_data: formData.role === 'KITCHEN_OWNER' ? licenseData.document_base64 : undefined,
        fssai_filename: formData.role === 'KITCHEN_OWNER' ? licenseData.filename : undefined,
      });
      setSuccess(message || 'Registration successful! Please check your email to verify your account.');
      setTimeout(() => navigate('/login'), 3500);
    } catch (err: any) {
      const msg = (Array.isArray(err?.errors) && err.errors.length > 0)
        ? err.errors.join(', ')
        : (err?.detail || err?.message || 'Registration failed');
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const updateField = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  return (
    <AuthLayout title="Create Account" subtitle="Join the KitchenVerse platform">
      {success ? (
        <div className="text-center">
          <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg text-sm mb-4">
            {success}
          </div>
          <Link to="/login" className="text-orange-600 font-medium hover:text-orange-700">
            Go to Login →
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="first_name" className="block text-sm font-medium text-gray-700 mb-1">
                First Name
              </label>
              <input
                id="first_name"
                type="text"
                required
                value={formData.first_name}
                onChange={(e) => updateField('first_name', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 transition text-sm"
                placeholder="John"
              />
            </div>
            <div>
              <label htmlFor="last_name" className="block text-sm font-medium text-gray-700 mb-1">
                Last Name
              </label>
              <input
                id="last_name"
                type="text"
                required
                value={formData.last_name}
                onChange={(e) => updateField('last_name', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 transition text-sm"
                placeholder="Doe"
              />
            </div>
          </div>

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
              Email Address
            </label>
            <input
              id="email"
              type="email"
              required
              value={formData.email}
              onChange={(e) => updateField('email', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 transition text-sm"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label htmlFor="role" className="block text-sm font-medium text-gray-700 mb-1">
              I am a...
            </label>
            <select
              id="role"
              value={formData.role}
              onChange={(e) => updateField('role', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 transition text-sm"
            >
              <option value="CUSTOMER">Customer</option>
              <option value="KITCHEN_OWNER">Kitchen Owner</option>
            </select>
          </div>

          {formData.role === 'KITCHEN_OWNER' && (
            <div className="space-y-3 p-3 bg-orange-50/60 border border-orange-200/70 rounded-lg">
              <h3 className="text-xs font-semibold text-orange-900 uppercase tracking-wider">
                Kitchen Information (Requires Admin Approval)
              </h3>
              <div>
                <label htmlFor="kitchen_name" className="block text-sm font-medium text-gray-700 mb-1">
                  Kitchen Name
                </label>
                <input
                  id="kitchen_name"
                  type="text"
                  required
                  value={formData.kitchen_name}
                  onChange={(e) => updateField('kitchen_name', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 transition text-sm bg-white"
                  placeholder="e.g. Royal Curry Kitchen"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="city" className="block text-sm font-medium text-gray-700 mb-1">
                    City
                  </label>
                  <input
                    id="city"
                    type="text"
                    required
                    value={formData.city}
                    onChange={(e) => updateField('city', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 transition text-sm bg-white"
                    placeholder="Bangalore"
                  />
                </div>
                <div>
                  <label htmlFor="phone_number" className="block text-sm font-medium text-gray-700 mb-1">
                    Phone (Optional)
                  </label>
                  <input
                    id="phone_number"
                    type="tel"
                    value={formData.phone_number}
                    onChange={(e) => updateField('phone_number', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 transition text-sm bg-white"
                    placeholder="+91 9876543210"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="address" className="block text-sm font-medium text-gray-700 mb-1">
                  Kitchen Address
                </label>
                <input
                  id="address"
                  type="text"
                  required
                  value={formData.address}
                  onChange={(e) => updateField('address', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 transition text-sm bg-white"
                  placeholder="123 Food Street, Indiranagar"
                />
              </div>

              {/* FSSAI License Document & Number Requirement */}
              <LicenseUploadSection
                initialLicenseNumber={licenseData.license_number}
                initialBusinessName={licenseData.business_name}
                initialExpiryDate={licenseData.expiry_date}
                required={true}
                onChange={(data) => setLicenseData(data)}
              />
            </div>
          )}

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              value={formData.password}
              onChange={(e) => updateField('password', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 transition text-sm"
              placeholder="••••••••"
            />
            {formData.password && passwordErrors.length > 0 && (
              <p className="text-xs text-red-500 mt-1">
                Needs: {passwordErrors.join(', ')}
              </p>
            )}
            {formData.password && passwordErrors.length === 0 && (
              <p className="text-xs text-green-600 mt-1">✓ Password meets requirements</p>
            )}
          </div>

          <div>
            <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-1">
              Confirm Password
            </label>
            <input
              id="confirmPassword"
              type="password"
              required
              value={formData.confirmPassword}
              onChange={(e) => updateField('confirmPassword', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 transition text-sm"
              placeholder="••••••••"
            />
            {formData.confirmPassword && formData.password !== formData.confirmPassword && (
              <p className="text-xs text-red-500 mt-1">Passwords do not match</p>
            )}
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
                Creating account...
              </span>
            ) : (
              'Create Account'
            )}
          </button>
        </form>
      )}

      {!success && (
        <p className="text-center text-sm text-gray-600 mt-6">
          Already have an account?{' '}
          <Link to="/login" className="text-orange-600 font-medium hover:text-orange-700">
            Sign in
          </Link>
        </p>
      )}
    </AuthLayout>
  );
}
