/**
 * Header da aplicação com botão de logout
 */
import { useNavigate } from 'react-router-dom';
import { logout } from '../services/authService';
import './Header.css';

export default function Header() {
  const navigate = useNavigate();

  const handleLogout = () => {
    console.log('[Header] 🚪 Fazendo logout...');
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <header className="app-header">
      <div className="header-content">
        <div className="header-title">
          <h1>📊 Dashboard ROI</h1>
        </div>

        <button
          onClick={handleLogout}
          className="logout-button"
          title="Fazer logout"
        >
          🚪 Sair
        </button>
      </div>
    </header>
  );
}

