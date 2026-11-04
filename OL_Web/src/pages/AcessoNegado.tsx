import { Link, useNavigate } from 'react-router-dom'
import { BRAND, BRAND_DARK, NAVY } from '../lib/cores'
import { Ban, ArrowLeft, LayoutDashboard } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'

/**
 * Tela exibida quando um usuário autenticado, mas sem o perfil necessário,
 * tenta acessar uma rota administrativa diretamente pela URL (task #34).
 *
 * Design (UI/UX): remete a algo bloqueado — selo com ícone de "proibido"
 * (Ban) sobre uma faixa de interdição diagonal em laranja/branco — com um
 * tom de texto mais descontraído, em vez de um 403 seco.
 */
export default function AcessoNegado() {
  const { user } = useAuth()
  const navigate = useNavigate()

  return (
    <div className="min-h-[70vh] flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center">
        {/* Selo de bloqueio sobre faixa de interdição decorativa */}
        <div className="relative mx-auto mb-7 w-28 h-28 flex items-center justify-center">
          <div
            className="absolute w-40 h-3.5 rounded-full rotate-[-8deg]"
            style={{
              backgroundImage: `repeating-linear-gradient(135deg, ${BRAND} 0 9px, #ffffff 9px 18px)`,
              boxShadow: '0 2px 10px rgba(33,150,243,0.28)',
            }}
            aria-hidden="true"
          />
          <div
            className="relative w-20 h-20 rounded-full flex items-center justify-center shadow-lg"
            style={{ background: `linear-gradient(135deg, ${NAVY} 0%, ${BRAND_DARK} 100%)` }}
          >
            <Ban size={30} className="text-[#2196F3]" strokeWidth={2.25} aria-hidden="true" />
          </div>
        </div>

        <span className="inline-block text-[11px] font-semibold tracking-wide uppercase text-brand bg-brand/10 px-2.5 py-1 rounded-full mb-3">
          Acesso restrito
        </span>

        <h1 className="text-2xl sm:text-3xl font-bold text-slate-800 tracking-tight mb-2">
          Calma aí, meu amigo!
        </h1>

        <p className="text-sm text-slate-500 leading-relaxed mb-1">
          Essa área é reservada para administradores do sistema
          {user?.perfil && (
            <> — seu perfil atual (<span className="font-medium text-slate-700">{user.perfil}</span>) não tem passe livre por aqui</>
          )}
          .
        </p>
        <p className="text-sm text-slate-500 mb-7">
          Se você acha que deveria ter acesso, dá um toque pro time de TI.
        </p>

        <div className="flex items-center justify-center gap-3">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-sm font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 transition-colors"
          >
            <ArrowLeft size={15} />
            Voltar
          </button>
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-sm font-semibold text-white bg-brand hover:bg-brand-dark transition-colors"
          >
            <LayoutDashboard size={15} />
            Ir para o Dashboard
          </Link>
        </div>
      </div>
    </div>
  )
}
