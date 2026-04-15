/**
 * LoginTest.tsx
 * Componente isolado para testar LOGIN sem scroll ou outros componentes
 *
 * Acesse em: http://localhost:5173/test/login
 */

import { useState } from 'react';
import './LoginTest.css';

interface LoginTestState {
  username: string;
  password: string;
  isLoading: boolean;
  response: unknown;
  error: string;
  token?: string;
  testResults: TestResult[];
}

interface TestResult {
  id: string;
  name: string;
  status: 'pending' | 'success' | 'error';
  response?: unknown;
  error?: string;
  timestamp: string;
}

export default function LoginTest() {
  const [state, setState] = useState<LoginTestState>({
    username: 'Admin',
    password: '#agenciatitan2026',
    isLoading: false,
    response: null,
    error: '',
    token: undefined,
    testResults: [],
  });

  // Test 1: Fazer login
  const handleLogin = async () => {
    setState(prev => ({ ...prev, isLoading: true, error: '', response: null }));

    const testId = `login-${Date.now()}`;
    const timestamp = new Date().toLocaleTimeString('pt-BR');

    try {
      const response = await fetch('http://localhost:8000/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: state.username,
          password: state.password,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Erro ao fazer login');
      }

      const token = data.access_token;

      setState(prev => ({
        ...prev,
        token,
        response: data,
        isLoading: false,
        testResults: [
          ...prev.testResults,
          {
            id: testId,
            name: '✅ LOGIN SUCESSO',
            status: 'success',
            response: data,
            timestamp,
          },
        ],
      }));
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Erro desconhecido';
      setState(prev => ({
        ...prev,
        error: errorMsg,
        isLoading: false,
        testResults: [
          ...prev.testResults,
          {
            id: testId,
            name: '❌ LOGIN FALHOU',
            status: 'error',
            error: errorMsg,
            timestamp,
          },
        ],
      }));
    }
  };

  // Test 2: Usar o token em requisição protegida
  const handleTestProtectedRoute = async () => {
    if (!state.token) {
      setState(prev => ({
        ...prev,
        error: 'Faça login primeiro para obter um token',
      }));
      return;
    }

    setState(prev => ({ ...prev, isLoading: true }));
    const testId = `protected-${Date.now()}`;
    const timestamp = new Date().toLocaleTimeString('pt-BR');

    try {
      const response = await fetch('http://localhost:8000/metrics/summary?period=24h', {
        headers: {
          'Authorization': `Bearer ${state.token}`,
        },
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Erro na requisição protegida');
      }

      setState(prev => ({
        ...prev,
        isLoading: false,
        testResults: [
          ...prev.testResults,
          {
            id: testId,
            name: '✅ REQUISIÇÃO PROTEGIDA SUCESSO',
            status: 'success',
            response: data,
            timestamp,
          },
        ],
      }));
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Erro desconhecido';
      setState(prev => ({
        ...prev,
        isLoading: false,
        testResults: [
          ...prev.testResults,
          {
            id: testId,
            name: '❌ REQUISIÇÃO PROTEGIDA FALHOU',
            status: 'error',
            error: errorMsg,
            timestamp,
          },
        ],
      }));
    }
  };

  // Test 3: Tentar com token inválido
  const handleTestInvalidToken = async () => {
    setState(prev => ({ ...prev, isLoading: true }));
    const testId = `invalid-token-${Date.now()}`;
    const timestamp = new Date().toLocaleTimeString('pt-BR');

    try {
      const response = await fetch('http://localhost:8000/metrics/summary?period=24h', {
        headers: {
          'Authorization': 'Bearer INVALID_TOKEN_12345',
        },
      });

      const data = await response.json();

      // Esperamos erro 401
      if (response.status === 401) {
        setState(prev => ({
          ...prev,
          isLoading: false,
          testResults: [
            ...prev.testResults,
            {
              id: testId,
              name: '✅ TOKEN INVÁLIDO DETECTADO (401)',
              status: 'success',
              response: data,
              timestamp,
            },
          ],
        }));
      } else {
        throw new Error('Esperava erro 401, mas recebeu ' + response.status);
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Erro desconhecido';
      setState(prev => ({
        ...prev,
        isLoading: false,
        testResults: [
          ...prev.testResults,
          {
            id: testId,
            name: '❌ TESTE FALHOU',
            status: 'error',
            error: errorMsg,
            timestamp,
          },
        ],
      }));
    }
  };

  // Test 4: Tentar sem token
  const handleTestNoToken = async () => {
    setState(prev => ({ ...prev, isLoading: true }));
    const testId = `no-token-${Date.now()}`;
    const timestamp = new Date().toLocaleTimeString('pt-BR');

    try {
      const response = await fetch('http://localhost:8000/metrics/summary?period=24h');
      const data = await response.json();

      // Esperamos erro 403 ou 401
      if (response.status === 403 || response.status === 401) {
        setState(prev => ({
          ...prev,
          isLoading: false,
          testResults: [
            ...prev.testResults,
            {
              id: testId,
              name: '✅ FALTA DE TOKEN DETECTADA (' + response.status + ')',
              status: 'success',
              response: data,
              timestamp,
            },
          ],
        }));
      } else {
        throw new Error('Esperava erro 403/401, mas recebeu ' + response.status);
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Erro desconhecido';
      setState(prev => ({
        ...prev,
        isLoading: false,
        testResults: [
          ...prev.testResults,
          {
            id: testId,
            name: '❌ TESTE FALHOU',
            status: 'error',
            error: errorMsg,
            timestamp,
          },
        ],
      }));
    }
  };

  const clearResults = () => {
    setState(prev => ({
      ...prev,
      testResults: [],
      response: null,
      error: '',
      token: undefined,
    }));
  };

  return (
    <div className="login-test-container">
      <div className="login-test-box">
        {/* HEADER */}
        <div className="login-test-header">
          <h1>🔐 TESTE DE LOGIN ISOLADO</h1>
          <p>Teste a autenticação separadamente do resto da aplicação</p>
        </div>

        {/* FORM */}
        <div className="login-test-form">
          <div className="form-group">
            <label>Usuário</label>
            <input
              type="text"
              value={state.username}
              onChange={(e) => setState(prev => ({ ...prev, username: e.target.value }))}
              disabled={state.isLoading}
              placeholder="Admin"
            />
          </div>

          <div className="form-group">
            <label>Senha</label>
            <input
              type="password"
              value={state.password}
              onChange={(e) => setState(prev => ({ ...prev, password: e.target.value }))}
              disabled={state.isLoading}
              placeholder="Senha"
            />
          </div>

          {state.error && (
            <div className="error-message">
              ❌ {state.error}
            </div>
          )}

          {state.token && (
            <div className="success-message">
              ✅ Token obtido com sucesso!
              <code>{state.token.substring(0, 50)}...</code>
            </div>
          )}
        </div>

        {/* BUTTONS */}
        <div className="login-test-buttons">
          <button
            onClick={handleLogin}
            disabled={state.isLoading}
            className="btn btn-primary"
          >
            {state.isLoading ? '⏳ Testando...' : '🔑 Teste: Fazer Login'}
          </button>

          <button
            onClick={handleTestProtectedRoute}
            disabled={state.isLoading || !state.token}
            className="btn btn-secondary"
          >
            🔒 Teste: Rota Protegida
          </button>

          <button
            onClick={handleTestInvalidToken}
            disabled={state.isLoading}
            className="btn btn-warning"
          >
            ⚠️ Teste: Token Inválido
          </button>

          <button
            onClick={handleTestNoToken}
            disabled={state.isLoading}
            className="btn btn-danger"
          >
            🚫 Teste: Sem Token
          </button>

          <button
            onClick={clearResults}
            disabled={state.isLoading}
            className="btn btn-reset"
          >
            🔄 Limpar Testes
          </button>
        </div>

        {/* RESULTS */}
        {state.testResults.length > 0 && (
          <div className="login-test-results">
            <h2>📊 Resultados dos Testes</h2>
            <div className="results-list">
              {state.testResults.map((result) => (
                <div
                  key={result.id}
                  className={`result-item result-${result.status}`}
                >
                  <div className="result-header">
                    <span className="result-name">{result.name}</span>
                    <span className="result-time">{result.timestamp}</span>
                  </div>

                  {result.response && (
                    <details className="result-details">
                      <summary>Ver Resposta</summary>
                      <pre>{JSON.stringify(result.response, null, 2)}</pre>
                    </details>
                  )}

                  {result.error && (
                    <div className="result-error">
                      <strong>Erro:</strong> {result.error}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* INFO */}
        <div className="login-test-info">
          <h3>ℹ️ Informações</h3>
          <ul>
            <li>✅ Login: Testa se as credenciais funcionam</li>
            <li>🔒 Rota Protegida: Testa se o token permite acessar endpoints</li>
            <li>⚠️ Token Inválido: Verifica se o sistema rejeita tokens inválidos</li>
            <li>🚫 Sem Token: Verifica se o sistema rejeita requisições sem token</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

