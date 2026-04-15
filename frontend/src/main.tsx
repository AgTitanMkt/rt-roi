import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import AppRouter from './router/AppRouter'
import { FilterProvider } from './context/FilterContext'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <FilterProvider>
      <AppRouter />
    </FilterProvider>
  </StrictMode>,
)


