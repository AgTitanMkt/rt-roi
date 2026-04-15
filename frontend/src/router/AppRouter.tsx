/**
 * Configuração de rotas da aplicação
 */
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from '../pages/LoginPage';
import LoginTest from '../pages/LoginTest';
import ProtectedRoute from '../components/ProtectedRoute';
import App from '../App';

export default function AppRouter() {
  return (
    <Router>
      <Routes>
        {/* Rota pública: Login */}
        <Route path="/login" element={<LoginPage />} />

        {/* Rota de teste: Teste de Login isolado */}
        <Route path="/test/login" element={<LoginTest />} />

        {/* Rota protegida: Dashboard */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <App />
            </ProtectedRoute>
          }
        />

        {/* Redirecionar rotas desconhecidas para home */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}

