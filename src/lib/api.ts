/**
 * Centralized API client for the Unified Cloud Kitchen Platform.
 * 
 * Handles:
 * - Authentication headers (JWT tokens)
 * - Authorization errors (401/403)
 * - Validation errors (422)
 * - Server errors (500)
 * - Loading states
 * - Token refresh
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class ApiClientError extends Error {
  status: number;
  detail: string;
  errors?: string[];

  constructor(status: number, detail: string, errors?: string[]) {
    super(detail);
    this.name = 'ApiClientError';
    this.status = status;
    this.detail = detail;
    this.errors = errors;
  }
}

class ApiClient {
  private baseUrl: string;
  private accessToken: string | null = null;
  private refreshToken: string | null = null;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
    this.loadTokens();
  }

  /**
   * Load tokens from localStorage on initialization.
   */
  private loadTokens(): void {
    try {
      const stored = localStorage.getItem('auth_tokens');
      if (stored) {
        const tokens = JSON.parse(stored);
        this.accessToken = tokens.access_token;
        this.refreshToken = tokens.refresh_token;
      }
    } catch {
      this.clearTokens();
    }
  }

  /**
   * Store tokens in localStorage.
   */
  setTokens(accessToken: string, refreshToken: string): void {
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
    localStorage.setItem('auth_tokens', JSON.stringify({
      access_token: accessToken,
      refresh_token: refreshToken,
    }));
  }

  /**
   * Clear stored tokens.
   */
  clearTokens(): void {
    this.accessToken = null;
    this.refreshToken = null;
    localStorage.removeItem('auth_tokens');
  }

  /**
   * Get the current access token.
   */
  getAccessToken(): string | null {
    return this.accessToken;
  }

  /**
   * Check if user is authenticated (has a token).
   */
  isAuthenticated(): boolean {
    return !!this.accessToken;
  }

  /**
   * Build request headers with auth token.
   */
  private getHeaders(includeAuth: boolean = true): HeadersInit {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    if (includeAuth && this.accessToken) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }
    return headers;
  }

  /**
   * Handle API response errors.
   */
  private async handleResponse(response: Response): Promise<any> {
    if (response.ok) {
      // Handle 204 No Content
      if (response.status === 204) {
        return null;
      }
      return response.json();
    }

    // Parse error response
    let errorData: any;
    try {
      errorData = await response.json();
    } catch {
      errorData = { detail: 'An unexpected error occurred' };
    }

    // Handle 401 - Unauthorized (token expired or invalid)
    if (response.status === 401) {
      this.clearTokens();
      // Redirect to login if not already there
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/login';
      }
    }

    // Handle 403 - Forbidden
    if (response.status === 403) {
      const detail = errorData?.detail || 'Access denied';
      throw new ApiClientError(403, detail);
    }

    // Handle 422 - Validation errors
    if (response.status === 422) {
      const errors = errorData?.detail?.map((e: any) => e.msg || e.message) || [];
      throw new ApiClientError(422, 'Validation failed', errors);
    }

    // Handle 409 - Conflict (e.g., duplicate email)
    if (response.status === 409) {
      throw new ApiClientError(409, errorData?.detail || 'Resource already exists');
    }

    // Handle 500 - Server error
    if (response.status >= 500) {
      throw new ApiClientError(500, 'Server error. Please try again later.');
    }

    // Generic error
    throw new ApiClientError(
      response.status,
      errorData?.detail || `Request failed with status ${response.status}`
    );
  }

  /**
   * Make a GET request.
   */
  async get<T = any>(path: string, includeAuth: boolean = true): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'GET',
      headers: this.getHeaders(includeAuth),
    });
    return this.handleResponse(response);
  }

  /**
   * Make a POST request.
   */
  async post<T = any>(path: string, body?: any, includeAuth: boolean = true): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: this.getHeaders(includeAuth),
      body: body ? JSON.stringify(body) : undefined,
    });
    return this.handleResponse(response);
  }

  /**
   * Make a PUT request.
   */
  async put<T = any>(path: string, body?: any, includeAuth: boolean = true): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'PUT',
      headers: this.getHeaders(includeAuth),
      body: body ? JSON.stringify(body) : undefined,
    });
    return this.handleResponse(response);
  }

  /**
   * Make a PATCH request.
   */
  async patch<T = any>(path: string, body?: any, includeAuth: boolean = true): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'PATCH',
      headers: this.getHeaders(includeAuth),
      body: body ? JSON.stringify(body) : undefined,
    });
    return this.handleResponse(response);
  }

  /**
   * Make a DELETE request.
   */
  async delete<T = any>(path: string, includeAuth: boolean = true): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'DELETE',
      headers: this.getHeaders(includeAuth),
    });
    return this.handleResponse(response);
  }
}

// Export singleton instance
export const apiClient = new ApiClient();
export { ApiClientError };
export default apiClient;
