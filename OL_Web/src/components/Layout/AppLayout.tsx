import { Suspense } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import ErrorBoundary from '../ErrorBoundary'
import PendenciasConfiguracao from '../PendenciasConfiguracao'

/** Mostrado enquanto o chunk da tela é baixado (as rotas usam React.lazy — ver App.tsx). */
function CarregandoTela() {
  return (
    <div className="flex items-center justify-center py-20" role="status" aria-label="Carregando tela">
      <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

export default function AppLayout() {
  const { pathname } = useLocation()
  return (
    <div className="min-h-screen flex" style={{ backgroundColor: '#f0f2f6' }}>
      <Sidebar />
      <main className="flex-1 ml-60 min-h-screen overflow-x-hidden">
        {/* Sem max-width fixo: o conteúdo ocupa a largura disponível (fluido) e só
         * ganha um teto (2000px, centralizado) em monitores muito largos, para o
         * texto/gráficos não esticarem demais. Resolve o espaço vazio à direita
         * em telas grandes que existia com o max-w-screen-xl fixo anterior. */}
        <div className="p-4 sm:p-6 w-full max-w-[2000px] mx-auto">
          <PendenciasConfiguracao />
          {/* Erro numa tela fica contido aqui: a Sidebar continua e o usuário
              pode navegar para outra tela (Q6). A `key` zera o erro ao trocar
              de rota. Também pega a falha ao baixar o chunk de uma tela lazy. */}
          <ErrorBoundary key={pathname}>
            <Suspense fallback={<CarregandoTela />}>
              <Outlet />
            </Suspense>
          </ErrorBoundary>
        </div>
      </main>
    </div>
  )
}
