/**
 * Serviço de autenticação
 * Gerencia login, tokens e localStorage
 */
import Cookies from 'js-cookie';

const API_BASE_URL = 'http://localhost:8000';
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

export async function login(credentials: LoginRequest): Promise<LoginResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',  // Incluir cookies nas requisições
      body: JSON.stringify(credentials),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Falha ao fazer login');
    }

    const data: LoginResponse = await response.json();

    console.log('[Auth] Token recebido, salvando...', data.access_token.substring(0, 20) + '...');

    // Salvar em localStorage (mais confiável)
    localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token);

    // Também salvar em cookie (para requisições)
    Cookies.set(TOKEN_COOKIE_NAME, data.access_token, {
      expires: TOKEN_EXPIRATION_DAYS,
      secure: import.meta.env.PROD,
      sameSite: 'lax',  // Mudado de 'strict' para 'lax'
      path: '/',
    });

    console.log('[Auth] Token salvo com sucesso');
    return data;
  } catch (error) {
    console.error('[Auth] Erro ao fazer login:', error);
    throw error;
  }
}

export function getToken(): string | undefined {
  // Tentar localStorage primeiro (mais confiável em SPA)
  const tokenFromStorage = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (tokenFromStorage) {
    console.log('[Auth] Token recuperado do localStorage');
    return tokenFromStorage;
  }

  // Fallback para cookie
  const tokenFromCookie = Cookies.get(TOKEN_COOKIE_NAME);
  if (tokenFromCookie) {
    console.log('[Auth] Token recuperado do cookie');
    // Sincronizar com localStorage
    localStorage.setItem(TOKEN_STORAGE_KEY, tokenFromCookie);
    return tokenFromCookie;
  }

  console.log('[Auth] Nenhum token encontrado');
  return undefined;
}

export function isAuthenticated(): boolean {
  const token = getToken();
  const result = !!token;
  console.log('[Auth] isAuthenticated:', result, token ? '(token encontrado)' : '(nenhum token)');
  return result;
}

export function logout(): void {
  console.log('[Auth] Fazendo logout...');
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  Cookies.remove(TOKEN_COOKIE_NAME, { path: '/' });
  console.log('[Auth] Logout concluído');
}

export function getAuthHeader(): Record<string, string> {
  const token = getToken();
  if (token) {
    return {
      Authorization: `Bearer ${token}`,
    };
  }
  return {};
}


