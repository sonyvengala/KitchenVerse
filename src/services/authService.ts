/**
 * Authentication service - frontend API calls for auth operations.
 */
import apiClient from '../lib/api';
import {
  User,
  AuthTokens,
  RegisterRequest,
  RegisterResponse,
  LoginRequest,
  MessageResponse,
  EmailStatusResponse,
} from '../types';

class AuthService {
  /**
   * Register a new user.
   */
  async register(data: RegisterRequest): Promise<RegisterResponse> {
    return apiClient.post<RegisterResponse>('/api/v1/auth/register', data, false);
  }

  /**
   * Login and receive tokens.
   */
  async login(email: string, password: string): Promise<AuthTokens> {
    return apiClient.post<AuthTokens>('/api/v1/auth/login', { email, password }, false);
  }

  /**
   * Logout (server-side acknowledgment).
   */
  async logout(): Promise<MessageResponse> {
    return apiClient.post<MessageResponse>('/api/v1/auth/logout');
  }

  /**
   * Get current user profile.
   */
  async getMe(): Promise<User> {
    return apiClient.get<User>('/api/v1/auth/me');
  }

  /**
   * Verify email with token.
   */
  async verifyEmail(token: string): Promise<MessageResponse> {
    return apiClient.post<MessageResponse>('/api/v1/auth/verify-email', { token }, false);
  }

  /**
   * Resend verification email with cooldown rate limiting.
   */
  async resendVerification(email?: string): Promise<{
    status: string;
    message: string;
    provider: string;
    email: string;
    cooldown_seconds: number;
  }> {
    return apiClient.post('/api/v1/auth/resend-verification', { email });
  }

  /**
   * Request password reset email.
   */
  async forgotPassword(email: string): Promise<EmailStatusResponse> {
    return apiClient.post<EmailStatusResponse>('/api/v1/auth/forgot-password', { email }, false);
  }

  /**
   * Reset password with token.
   */
  async resetPassword(token: string, newPassword: string): Promise<MessageResponse> {
    return apiClient.post<MessageResponse>('/api/v1/auth/reset-password', {
      token,
      new_password: newPassword,
    }, false);
  }

  /**
   * Change password (authenticated).
   */
  async changePassword(currentPassword: string, newPassword: string): Promise<MessageResponse> {
    return apiClient.post<MessageResponse>('/api/v1/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
  }
}

export default new AuthService();
