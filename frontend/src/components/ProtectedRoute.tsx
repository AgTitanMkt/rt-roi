/**
 * Componente para proteger rotas que requerem autenticação
 * Redireciona para login se o usuário não tiver token válido
 */
import { useMemo } from 'react';
import { Navigate } from 'react-router-dom';
import { isAuthenticated, getToken } from '../services/authService';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  // Memoize para evitar re-renders desnecessários
  const authenticated = useMemo(() => {
    const token = getToken();
    const isAuth = isAuthenticated();

    console.log('[ProtectedRoute] Verificando autenticação...');
    console.log('[ProtectedRoute] Token:', token ? token.substring(0, 20) + '...' : 'não encontrado');
    console.log('[ProtectedRoute] isAuthenticated():', isAuth);

    if (isAuth) {
      console.log('[ProtectedRoute] ✅ Usuário autenticado, permitindo acesso');
    } else {
      console.log('[ProtectedRoute] ❌ Usuário não autenticado, será redirecionado');
    }

    return isAuth;
  }, []);


  // Se não autenticado, redirecionar
  if (!authenticated) {
    console.log('[ProtectedRoute] Redirecionando para /login');
    return <Navigate to="/login" replace />;
  }

  // Se autenticado, renderizar o conteúdo
  return <>{children}</>;
}

