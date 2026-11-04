import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle } from 'lucide-react'
import { CHAVE_QUERY_PENDENCIAS, parametrosApi } from '../api/parametros'
import { useAuth } from '../contexts/AuthContext'
import { perfilEmAlgum } from '../lib/perfil'

/**
 * Alerta global (todas as telas, todos os perfis) para configuração obrigatória
 * que falta — hoje, o CNPJ do distribuidor: sem ele os serviços não geram
 * retorno, espelho, cancelamento nem estoque. Só quem pode configurar recebe o
 * link para a Parametrização; os demais são orientados a avisar quem pode.
 */
export default function PendenciasConfiguracao() {
  const { user } = useAuth()
  const podeConfigurar = perfilEmAlgum(user?.perfil, ['Administrador', 'Gerente Comercial'])

  const { data: pendencias } = useQuery({
    queryKey: CHAVE_QUERY_PENDENCIAS,
    queryFn: parametrosApi.pendencias,
    enabled: !!user,
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
  })

  if (!pendencias?.length) return null

  return (
    <div className="mb-4 space-y-2">
      {pendencias.map((p) => (
        <div
          key={p.chave}
          role="alert"
          className="flex items-start gap-2.5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
        >
          <AlertTriangle size={16} className="mt-0.5 shrink-0 text-amber-500" />
          <div className="min-w-0">
            <p className="font-semibold">{p.titulo}</p>
            <p className="text-amber-700">
              {p.mensagem}{' '}
              {podeConfigurar ? (
                <Link to="/parametrizacao" className="font-medium underline hover:text-amber-900">
                  Configurar agora
                </Link>
              ) : (
                'Avise um Administrador ou Gerente Comercial.'
              )}
            </p>
          </div>
        </div>
      ))}
    </div>
  )
}
