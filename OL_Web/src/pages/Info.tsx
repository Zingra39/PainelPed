import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { errosApi } from '../api/erros'
import StatusBadge from '../components/StatusBadge'
import { Th, TableFeedback } from '../components/Table'
import { Info as InfoIcon, Users, ListChecks, Search, ArrowRight, AlertTriangle } from 'lucide-react'

const FLUXO_OPERACIONAL = [
  'Pedido Enviado', 'Transmitido', 'Retorno Gerado', 'Espelho Gerado'
]

// const FLUXO_ERP = ['Não Transmitido', 'Transmitido', 'Faturado', 'Cancelado']

const PERFIS = [
  {
    nome: 'Operador Logístico',
    descricao:
      'Atua no dia a dia da Triagem e rastreamento dos pedidos: consulta pedidos, itens e ocorrências, baixa arquivos gerados e realiza as ações manuais (transmitir, reprocessar, gerar retorno/espelho/cancelamento).',
  },
  {
    nome: 'Gerente Comercial',
    descricao:
      'Acesso somente leitura, focado em dashboards, indicadores de faturamento e desempenho comercial. Não executa ações operacionais sobre os pedidos.',
  },
  {
    nome: 'Administrador',
    descricao:
      'Controle total do sistema: além das ações operacionais, gerencia usuários, indústrias e o monitoramento dos serviços Python responsáveis pela importação e geração de arquivos.',
  },
]

export default function Info() {
  const [busca, setBusca] = useState('')

  const { data: erros, isLoading, isError, error } = useQuery({
    queryKey: ['erros'],
    queryFn: () => errosApi.list(),
  })

  const errosFiltrados = (erros ?? []).filter((e) =>
    !busca || (e.descricao ?? '').toLowerCase().includes(busca.toLowerCase()) || String(e.codigo_erp ?? '').includes(busca)
  )

  return (
    <div>
      <div className="flex items-center gap-2 mb-5">
        <InfoIcon size={20} className="text-slate-400" />
        <h1 className="text-xl font-semibold text-slate-800">Informações do Sistema</h1>
      </div>

      {/* Fluxo de pedidos */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 mb-4">
        <div className="flex items-center gap-2 font-semibold text-slate-700 text-sm mb-4">
          <ListChecks size={15} className="text-slate-400" />
          Fluxo de Pedidos OL
        </div>

        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">Fluxo OL</p>
        <div className="flex items-center gap-2 flex-wrap mb-5">
          {FLUXO_OPERACIONAL.map((s, i) => (
            <div key={s} className="flex items-center gap-2">
              <StatusBadge status={s} />
              {i < FLUXO_OPERACIONAL.length - 1 && <ArrowRight size={13} className="text-slate-300" />}
            </div>
          ))}
        </div>
      </div>

      {/* Perfis de usuário */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 mb-4">
        <div className="flex items-center gap-2 font-semibold text-slate-700 text-sm mb-4">
          <Users size={15} className="text-slate-400" />
          Perfis de Usuário
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {PERFIS.map((p) => (
            <div key={p.nome} className="border border-slate-100 rounded-lg p-4">
              <p className="text-sm font-semibold text-slate-700 mb-1.5">{p.nome}</p>
              <p className="text-xs text-slate-500 leading-relaxed">{p.descricao}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Erros do sistema */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 flex-wrap gap-2">
          <div className="flex items-center gap-2 font-semibold text-slate-700 text-sm">
            <AlertTriangle size={15} className="text-slate-400" />
            Codigo motivo de não atendimento
          </div>
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-300" />
            <input
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Buscar por código ou descrição"
              className="pl-8 pr-3 py-1.5 rounded-lg border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500 w-64"
            />
          </div>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50">
              <Th className="w-32">Código ERP</Th>
              <Th>Descrição</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            <TableFeedback
              colunas={2}
              linhas={5}
              isLoading={isLoading}
              isError={isError && !erros}
              error={error}
              isEmpty={errosFiltrados.length === 0}
              vazio="Nenhum erro catalogado encontrado"
            />
            {errosFiltrados.map((e) => (
              <tr key={e.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-mono text-xs text-slate-600">{e.codigo_erp ?? '—'}</td>
                <td className="px-4 py-3 text-slate-700">{e.descricao ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
