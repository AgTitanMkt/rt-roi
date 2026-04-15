/**
 * Componente para proteger rotas que requerem autenticação
 * Redireciona para login se o usuário não tiver token válido
 */
import { useEffect, useState, useMemo } from 'react';
import { Navigate } from 'react-router-dom';
import { isAuthenticated, getToken } from '../services/authService';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const [isChecking, setIsChecking] = useState(true);

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

  useEffect(() => {
    setIsChecking(false);
  }, []);

  // Enquanto verifica, mostrar loading
  if (isChecking) {
    return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
      <div>Verificando autenticação...</div>
    </div>;
  }

  // Se não autenticado, redirecionar
  if (!authenticated) {
    console.log('[ProtectedRoute] Redirecionando para /login');
    return <Navigate to="/login" replace />;
  }

  // Se autenticado, renderizar o conteúdo
  return <>{children}</>;
}

