import { lazy } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './contexts/AuthContext'
import PrivateRoute from './components/PrivateRoute'
import RoleRoute from './components/RoleRoute'
import AppLayout from './components/Layout/AppLayout'
import ErrorBoundary from './components/ErrorBoundary'
import Login from './pages/Login'

// Cada tela vira um chunk próprio (R3 da auditoria): antes tudo saía num único
// JS de ~850 KB, e o recharts do Dashboard era baixado até por quem só abria a
// Triagem. O <Suspense> que mostra o carregamento fica no AppLayout, em volta
// do <Outlet>, para a Sidebar continuar na tela durante a troca de rota.
// O Login continua no bundle principal: é a primeira tela de quem chega.
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Confeccao = lazy(() => import('./pages/Pedidos/Confeccao'))
const Rastreamento = lazy(() => import('./pages/Pedidos/Rastreamento'))
const Historico = lazy(() => import('./pages/Pedidos/Historico'))
const PedidoDetail = lazy(() => import('./pages/Pedidos/PedidoDetail'))
const Ocorrencias = lazy(() => import('./pages/Ocorrencias'))
const Arquivos = lazy(() => import('./pages/Arquivos'))
const Usuarios = lazy(() => import('./pages/Usuarios'))
const Servicos = lazy(() => import('./pages/Servicos'))
const Parametrizacao = lazy(() => import('./pages/Parametrizacao'))
const IndustriasList = lazy(() => import('./pages/Industrias/IndustriasList'))
const IndustriaDetail = lazy(() => import('./pages/Industrias/IndustriaDetail'))
const Info = lazy(() => import('./pages/Info'))

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          {/* Última linha de defesa: erro fora das telas (layout, login). */}
          <ErrorBoundary>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route element={<PrivateRoute />}>
              {/* O ErrorBoundary das telas fica dentro do AppLayout, em volta do
                  <Outlet>: um erro numa página não derruba mais a Sidebar (Q6). */}
              <Route element={<AppLayout />}>
                <Route index element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/pedidos" element={<Navigate to="/pedidos/confeccao" replace />} />
                <Route path="/pedidos/confeccao" element={<Confeccao />} />
                <Route path="/pedidos/rastreamento" element={<Rastreamento />} />
                <Route path="/pedidos/historico" element={<Historico />} />
                <Route path="/pedidos/:id" element={<PedidoDetail />} />
                <Route path="/ocorrencias" element={<Ocorrencias />} />
                <Route path="/arquivos" element={<Arquivos />} />
                {/* Rotas administrativas — task #34: bloqueadas por perfil antes de
                    qualquer chamada à API, com tela de acesso negado. */}
                <Route element={<RoleRoute perfis={['Administrador']} />}>
                  <Route path="/usuarios" element={<Usuarios />} />
                  <Route path="/servicos" element={<Servicos />} />
                  <Route path="/industrias" element={<IndustriasList />} />
                  <Route path="/industrias/:id" element={<IndustriaDetail />} />
                </Route>
                <Route element={<RoleRoute perfis={['Administrador', 'Gerente Comercial']} />}>
                  <Route path="/parametrizacao" element={<Parametrizacao />} />
                </Route>
                <Route path="/info" element={<Info />} />
              </Route>
            </Route>
          </Routes>
          </ErrorBoundary>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
