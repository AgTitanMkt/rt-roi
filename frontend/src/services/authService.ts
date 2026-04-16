/**
 * Serviço de autenticação
 * Gerencia login, tokens e localStorage
 */
import Cookies from 'js-cookie';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');
const TOKEN_STORAGE_KEY = 'auth_token';
const TOKEN_COOKIE_NAME = 'auth_token';
const TOKEN_EXPIRATION_DAYS = 3;

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthUser {
  id: number;
  username: string;
  role: 'admin' | 'user';
  sector?: 'nt' | 'yt' | 'fb' | null;
  exp: number;
}

const parseJwtPayload = (token: string): AuthUser | null => {
  try {
    const payloadBase64 = token.split('.')[1];
    if (!payloadBase64) return null;
    const payloadJson = atob(payloadBase64.replace(/-/g, '+').replace(/_/g, '/'));
    const parsed = JSON.parse(payloadJson) as Partial<AuthUser>;

    if (
      typeof parsed.id !== 'number' ||
      typeof parsed.username !== 'string' ||
      (parsed.role !== 'admin' && parsed.role !== 'user') ||
      typeof parsed.exp !== 'number'
    ) {
      return null;
    }

    return parsed as AuthUser;
  } catch {
    return null;
  }
};

const persistToken = (token: string): void => {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
  Cookies.set(TOKEN_COOKIE_NAME, token, {
    expires: TOKEN_EXPIRATION_DAYS,
    secure: import.meta.env.PROD,
    sameSite: 'lax',
    path: '/',
  });
};

const clearToken = (): void => {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  Cookies.remove(TOKEN_COOKIE_NAME, { path: '/' });
};

export async function login(credentials: LoginRequest): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify(credentials),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error((error as { detail?: string }).detail || 'Falha ao fazer login');
  }

  const data: LoginResponse = await response.json();
  persistToken(data.access_token);
  return data;
}

export function getToken(): string | undefined {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY) || Cookies.get(TOKEN_COOKIE_NAME);
  if (!token) return undefined;

  const user = parseJwtPayload(token);
  const nowInSeconds = Math.floor(Date.now() / 1000);
  if (!user || user.exp <= nowInSeconds) {
    clearToken();
    return undefined;
  }

  if (!localStorage.getItem(TOKEN_STORAGE_KEY)) {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
  }

  return token;
}

export function getCurrentUser(): AuthUser | null {
  const token = getToken();
  if (!token) return null;
  return parseJwtPayload(token);
}

export function isAuthenticated(): boolean {
  return !!getCurrentUser();
}

export function isAdmin(): boolean {
  return getCurrentUser()?.role === 'admin';
}

export function logout(): void {
  clearToken();
}

export function getAuthHeader(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
