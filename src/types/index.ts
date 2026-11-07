/**
 * TypeScript types for KitchenVerse
 */

// =============================================
// User & Auth Types
// =============================================

export type UserRole = 'CUSTOMER' | 'KITCHEN_OWNER' | 'ADMIN';
export type UserStatus = 'ACTIVE' | 'INACTIVE' | 'SUSPENDED' | 'PENDING_VERIFICATION';

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  role: UserRole;
  status: UserStatus;
  is_email_verified: boolean;
  is_verified?: boolean;
  email_verified_at: string | null;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export type LicenseStatus = 'PENDING_REVIEW' | 'CORRECTION_REQUIRED' | 'VERIFIED' | 'REJECTED' | 'EXPIRED';

export interface KitchenLicenseDocument {
  id: number;
  license_id: number;
  original_filename: string;
  file_size_bytes: number;
  mime_type: string;
  file_hash_sha256?: string | null;
  version: number;
  is_current: boolean;
  uploaded_at: string;
}

export interface KitchenLicense {
  id: number;
  kitchen_id: number;
  license_number: string;
  business_name?: string | null;
  status: LicenseStatus;
  issued_date?: string | null;
  expiry_date?: string | null;
  rejection_reason?: string | null;
  correction_reason?: string | null;
  is_duplicate_flagged: boolean;
  duplicate_notes?: string | null;
  ocr_extracted_number?: string | null;
  ocr_extracted_name?: string | null;
  ocr_extracted_expiry?: string | null;
  ocr_confidence?: number | null;
  verified_at?: string | null;
  verified_by_user_id?: number | null;
  created_at: string;
  updated_at: string;
  documents?: KitchenLicenseDocument[];
  current_document?: KitchenLicenseDocument | null;
}

export interface RegisterRequest {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  phone_number?: string;
  kitchen_name?: string;
  address?: string;
  city?: string;
  fssai_license_number?: string;
  fssai_business_name?: string;
  fssai_expiry_date?: string;
  fssai_document_data?: string;
  fssai_filename?: string;
}

export interface RegisterResponse {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  status: UserStatus;
  message: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface VerifyEmailRequest {
  token: string;
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface ResetPasswordRequest {
  token: string;
  new_password: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface MessageResponse {
  message: string;
  detail?: string;
}

export interface EmailStatusResponse {
  message: string;
  email_configured: boolean;
  provider: string;
}

export interface ApiError {
  detail: string;
  errors?: string[];
}

// =============================================
// Auth State
// =============================================

export interface AuthState {
  user: User | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}
