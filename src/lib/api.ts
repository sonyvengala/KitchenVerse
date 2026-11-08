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

const rawApiUrl = import.meta.env.VITE_API_URL;

function resolveApiBaseUrl(): string {
  // 1. Explicitly configured VITE_API_URL
  if (rawApiUrl !== undefined && rawApiUrl !== '') {
    return String(rawApiUrl).replace(/\/+$/, '');
  }

  // 2. In browser runtime
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    // Local development - use Vite dev server proxy at /api
    if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '0.0.0.0') {
      return '';
    }
    // Remote/Production deployment (e.g. *.vercel.app) without explicit VITE_API_URL
    return 'https://kitchenverse.onrender.com';
  }

  // 3. Node/SSR fallback
  return 'http://localhost:8000';
}

const API_BASE_URL = resolveApiBaseUrl();

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
  private inFlightRequests: Map<string, Promise<any>> = new Map();
  private cache: Map<string, { data: any; expiry: number }> = new Map();
  private readonly DEFAULT_CACHE_TTL = 8000; // 8 seconds TTL for GET requests

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
    this.loadTokens();
  }

  /**
   * Get the current resolved API base URL.
   */
  getBaseUrl(): string {
    return this.baseUrl;
  }

  /**
   * Invalidate all or matching cache entries upon state mutation.
   */
  clearCache(pattern?: string): void {
    if (!pattern) {
      this.cache.clear();
      return;
    }
    for (const key of this.cache.keys()) {
      if (key.includes(pattern)) {
        this.cache.delete(key);
      }
    }
  }

  /**
   * Load tokens from storage on initialization, route transitions, or requests.
   * Checks tab-scoped sessionStorage first to allow concurrent multi-role tabs.
   */
  loadTokens(): void {
    try {
      const path = typeof window !== 'undefined' ? window.location.pathname : '';
      let roleScope: string | null = null;
      if (path.startsWith('/admin')) {
        roleScope = 'ADMIN';
      } else if (path.startsWith('/kitchen')) {
        roleScope = 'KITCHEN_OWNER';
      } else if (path.startsWith('/customer')) {
        roleScope = 'CUSTOMER';
      }

      let stored: string | null = null;

      // 1. Role-scoped tab sessionStorage (dedicated tab for this portal)
      if (roleScope && typeof sessionStorage !== 'undefined') {
        stored = sessionStorage.getItem(`auth_tokens_${roleScope}`);
      }

      // 2. Generic tab sessionStorage
      if (!stored && typeof sessionStorage !== 'undefined') {
        stored = sessionStorage.getItem('auth_tokens');
      }

      // 3. Role-scoped localStorage (persisted for this browser profile)
      if (!stored && roleScope && typeof localStorage !== 'undefined') {
        stored = localStorage.getItem(`auth_tokens_${roleScope}`);
      }

      // 4. Fallback to generic localStorage
      if (!stored && typeof localStorage !== 'undefined') {
        stored = localStorage.getItem('auth_tokens');
      }

      if (stored) {
        const tokens = JSON.parse(stored);
        this.accessToken = tokens.access_token || null;
        this.refreshToken = tokens.refresh_token || null;
      } else {
        this.accessToken = null;
        this.refreshToken = null;
      }
    } catch {
      this.accessToken = null;
      this.refreshToken = null;
    }
  }

  /**
   * Store tokens in sessionStorage (per-tab) and localStorage (per-profile).
   */
  setTokens(accessToken: string, refreshToken: string, role?: string): void {
    if (!accessToken || accessToken === 'cookie-session' || accessToken === 'null' || accessToken === 'undefined') {
      return;
    }
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
    const payload = JSON.stringify({
      access_token: accessToken,
      refresh_token: refreshToken,
      role: role || null,
    });

    try {
      if (typeof sessionStorage !== 'undefined') {
        sessionStorage.setItem('auth_tokens', payload);
        if (role) {
          sessionStorage.setItem(`auth_tokens_${role}`, payload);
        }
      }
      if (typeof localStorage !== 'undefined') {
        if (role) {
          localStorage.setItem(`auth_tokens_${role}`, payload);
        } else {
          localStorage.setItem('auth_tokens', payload);
        }
      }
    } catch {
      // Ignore private storage limitations
    }
  }

  /**
   * Clear stored tokens for this tab and role.
   */
  clearTokens(role?: string): void {
    this.accessToken = null;
    this.refreshToken = null;
    try {
      if (typeof sessionStorage !== 'undefined') {
        sessionStorage.removeItem('auth_tokens');
        if (role) {
          sessionStorage.removeItem(`auth_tokens_${role}`);
        }
      }
      if (typeof localStorage !== 'undefined') {
        if (role) {
          localStorage.removeItem(`auth_tokens_${role}`);
        } else {
          localStorage.removeItem('auth_tokens');
        }
      }
    } catch {
      // Ignore
    }
  }

  /**
   * Get the current access token, reloading from storage to ensure freshest tab/role context.
   */
  getAccessToken(): string | null {
    this.loadTokens();
    return this.accessToken;
  }

  /**
   * Check if user is authenticated (has a token).
   */
  isAuthenticated(): boolean {
    return !!this.getAccessToken();
  }

  /**
   * Build request headers with auth token.
   */
  private getHeaders(includeAuth: boolean = true, isFormData: boolean = false): Record<string, string> {
    const headers: Record<string, string> = {};
    if (!isFormData) {
      headers['Content-Type'] = 'application/json';
    }
    const token = this.getAccessToken();
    if (includeAuth && token && token !== 'cookie-session' && token !== 'null' && token !== 'undefined') {
      headers['Authorization'] = `Bearer ${token}`;
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
    let errorData: any = null;
    const rawText = await response.text().catch(() => '');
    if (rawText) {
      try {
        errorData = JSON.parse(rawText);
      } catch {
        errorData = null;
      }
    }

    let errorMessage = '';
    let errorList: string[] | undefined = undefined;

    if (typeof errorData?.detail === 'string') {
      errorMessage = errorData.detail;
    } else if (Array.isArray(errorData?.detail)) {
      const items = errorData.detail.map((e: any) =>
        typeof e === 'string' ? e : (e.msg || e.message || JSON.stringify(e))
      );
      errorList = items;
      errorMessage = items.join(', ');
    } else if (errorData?.detail && typeof errorData.detail === 'object') {
      errorMessage = errorData.detail.msg || errorData.detail.message || JSON.stringify(errorData.detail);
    } else if (typeof errorData?.message === 'string') {
      errorMessage = errorData.message;
    }

    // Handle 401 - Unauthorized (token expired, invalid credentials)
    if (response.status === 401) {
      this.clearTokens();
      const isAuthCheck = response.url.includes('/api/v1/auth/me');
      const authPaths = ['/login', '/register', '/forgot-password', '/reset-password'];
      const path = typeof window !== 'undefined' ? window.location.pathname : '';
      const onAuthPage = authPaths.some(p => path.includes(p));
      const isProtectedPage = (
        path.startsWith('/admin') ||
        path === '/kitchen' ||
        path.startsWith('/kitchen/') ||
        path.startsWith('/kitchen-owner') ||
        path.startsWith('/orders') ||
        path.startsWith('/checkout')
      );
      if (!onAuthPage && !isAuthCheck && isProtectedPage && typeof window !== 'undefined') {
        window.location.href = '/login';
      }
      throw new ApiClientError(401, errorMessage || 'Invalid email or password');
    }

    // Handle 403 - Forbidden
    if (response.status === 403) {
      throw new ApiClientError(403, errorMessage || 'Access denied. Your account may be inactive or not yet approved.');
    }

    // Handle 404 - Not found
    if (response.status === 404) {
      const isAuth = response.url.includes('/auth') || response.url.includes('/login');
      const notFoundMessage = isAuth
        ? 'Authentication service endpoint not found (404). Please ensure the backend server is running and API URL is configured correctly.'
        : 'Resource not found';
      throw new ApiClientError(404, errorMessage || notFoundMessage);
    }

    // Handle 422 - Validation errors
    if (response.status === 422) {
      throw new ApiClientError(422, errorMessage || 'Please check your input and try again', errorList);
    }

    // Handle 429 - Rate limit
    if (response.status === 429) {
      throw new ApiClientError(429, errorMessage || 'Too many requests. Please wait before trying again.');
    }

    // Handle 400 / 409 - Bad request / Conflict (e.g., duplicate email)
    if (response.status === 400 || response.status === 409) {
      throw new ApiClientError(response.status, errorMessage || 'Request could not be processed');
    }

    // Handle 500+ - Server/proxy error
    if (response.status >= 500) {
      // Empty body usually means Vite proxy couldn't reach the backend
      if (!rawText) {
        throw new ApiClientError(
          response.status,
          'Cannot connect to server. Please ensure the backend server is running.'
        );
      }
      throw new ApiClientError(response.status, errorMessage || 'Server error. Please try again later.');
    }

    // Generic error
    throw new ApiClientError(
      response.status,
      errorMessage || `Request failed with status ${response.status}`
    );
  }

  /**
   * Make a GET request with in-flight deduplication and short-lived caching.
   * @param path The endpoint path
   * @param includeAuth Whether to include Authorization header
   * @param useCache Whether to use/populate the memory cache (default: true)
   */
  async get<T = any>(path: string, includeAuth: boolean = true, useCache: boolean = true): Promise<T> {
    const cacheKey = `${includeAuth ? 'auth:' : 'noauth:'}${path}`;
    const now = Date.now();

    // 1. Check TTL cache
    if (useCache) {
      const cached = this.cache.get(cacheKey);
      if (cached && cached.expiry > now) {
        return cached.data as T;
      }
    }

    // 2. Check for in-flight request deduplication
    if (this.inFlightRequests.has(cacheKey)) {
      return this.inFlightRequests.get(cacheKey) as Promise<T>;
    }

    // 3. Dispatch network request
    const requestPromise = (async () => {
      try {
        const response = await fetch(`${this.baseUrl}${path}`, {
          method: 'GET',
          headers: this.getHeaders(includeAuth),
          credentials: 'include',
        });
        const data = await this.handleResponse(response);

        // Store in short-lived cache
        if (useCache) {
          this.cache.set(cacheKey, {
            data,
            expiry: Date.now() + this.DEFAULT_CACHE_TTL,
          });
        }
        return data as T;
      } catch (err: any) {
        if (err instanceof ApiClientError) throw err;
        throw new ApiClientError(0, err.message || 'Cannot connect to server. Please ensure the backend server is running.');
      } finally {
        this.inFlightRequests.delete(cacheKey);
      }
    })();

    this.inFlightRequests.set(cacheKey, requestPromise);
    return requestPromise;
  }

  /**
   * Make a POST request (invalidates cache).
   */
  async post<T = any>(path: string, body?: any, includeAuth: boolean = true): Promise<T> {
    this.clearCache();
    const isFormData = typeof FormData !== 'undefined' && body instanceof FormData;
    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        method: 'POST',
        headers: this.getHeaders(includeAuth, isFormData),
        body: isFormData ? body : (body !== undefined ? JSON.stringify(body) : undefined),
        credentials: 'include',
      });
      return await this.handleResponse(response);
    } catch (err: any) {
      if (err instanceof ApiClientError) throw err;
      throw new ApiClientError(0, err.message || 'Cannot connect to server. Please verify backend is running.');
    }
  }

  /**
   * Make a PUT request (invalidates cache).
   */
  async put<T = any>(path: string, body?: any, includeAuth: boolean = true): Promise<T> {
    this.clearCache();
    const isFormData = typeof FormData !== 'undefined' && body instanceof FormData;
    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        method: 'PUT',
        headers: this.getHeaders(includeAuth, isFormData),
        body: isFormData ? body : (body !== undefined ? JSON.stringify(body) : undefined),
        credentials: 'include',
      });
      return await this.handleResponse(response);
    } catch (err: any) {
      if (err instanceof ApiClientError) throw err;
      throw new ApiClientError(0, err.message || 'Cannot connect to server. Please verify backend is running.');
    }
  }

  /**
   * Make a PATCH request (invalidates cache).
   */
  async patch<T = any>(path: string, body?: any, includeAuth: boolean = true): Promise<T> {
    this.clearCache();
    const isFormData = typeof FormData !== 'undefined' && body instanceof FormData;
    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        method: 'PATCH',
        headers: this.getHeaders(includeAuth, isFormData),
        body: isFormData ? body : (body !== undefined ? JSON.stringify(body) : undefined),
        credentials: 'include',
      });
      return await this.handleResponse(response);
    } catch (err: any) {
      if (err instanceof ApiClientError) throw err;
      throw new ApiClientError(0, err.message || 'Cannot connect to server. Please verify backend is running.');
    }
  }

  /**
   * Make a DELETE request (invalidates cache).
   */
  async delete<T = any>(path: string, includeAuth: boolean = true): Promise<T> {
    this.clearCache();
    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        method: 'DELETE',
        headers: this.getHeaders(includeAuth),
        credentials: 'include',
      });
      return await this.handleResponse(response);
    } catch (err: any) {
      if (err instanceof ApiClientError) throw err;
      throw new ApiClientError(0, err.message || 'Cannot connect to server. Please verify backend is running.');
    }
  }
}

// Export singleton instance
export const apiClient = new ApiClient();
export { ApiClientError };
export default apiClient;
