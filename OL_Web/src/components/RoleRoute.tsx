import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { perfilEmAlgum } from '../lib/perfil'
import AcessoNegado from '../pages/AcessoNegado'

interface RoleRouteProps {
  /** Perfis autorizados a acessar as rotas filhas (ex.: ['Administrador']). */
  perfis: string[]
}

/**
 * Guard de rota por perfil — task #34 (Azure Boards).
 *
 * Antes: rotas administrativas (/usuarios, /servicos, /industrias) eram só
 * escondidas da sidebar (Sidebar.tsx filtra por isAdmin), mas continuavam
 * acessíveis por URL direta — a página renderizava, chamava a API, tomava
 * 403 do backend (`require_perfis` já protege corretamente todos os
 * endpoints desses três routers — conferido em OL_API/app/routers/
 * usuarios.py, servicos.py e industrias.py) e mostrava spinner infinito ou
 * erro genérico.
 *
 * Agora: o guard barra o acesso antes de qualquer chamada à API e mostra a
 * tela de acesso negado imediatamente, sem sequer montar a página protegida.
 *
 * Uso: nichado dentro de <PrivateRoute /> (que já garante usuário
 * autenticado) — aqui só validamos o perfil dele.
 */
export default function RoleRoute({ perfis }: RoleRouteProps) {
  const { user } = useAuth()

  if (!user) return <Navigate to="/login" replace />
  // perfilEmAlgum e não includes(): o nome vem do banco e pode diferir na
  // acentuação/caixa — ver lib/perfil.ts.
  if (!perfilEmAlgum(user.perfil, perfis)) return <AcessoNegado />

  return <Outlet />
}
