import { useState, type FormEvent } from 'react'
import { BRAND, BRAND_DARK, NAVY } from '../lib/cores'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { Eye, EyeOff, Mail, Lock, ArrowRight, PackageCheck, FileCheck2, Activity } from 'lucide-react'
import dispfarmIcone from '../assets/DISPFARM ICONE.png'
import dispfarmWatermark from '../assets/DISPFARM BRANCA.png'
import { apiErr } from '../lib/apiError'

// Paleta DispFarm (Docs/Art/Group 46.png)
const BLUE_LIGHT = '#2196F3'

const DESTAQUES = [
  { icon: PackageCheck, titulo: 'Pedidos OL em tempo real', texto: 'Acompanhe recebimento, transmissão e faturamento num só lugar.' },
  { icon: FileCheck2, titulo: 'Retornos automatizados', texto: 'Geração e envio de retorno para as indústrias, sem retrabalho.' },
  { icon: Activity, titulo: 'Monitoramento dos serviços', texto: 'Visibilidade imediata de ocorrências e status dos processos.' },
]

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [showSenha, setShowSenha] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, senha)
      navigate('/dashboard', { replace: true })
    } catch (err: unknown) {
      setError(apiErr(err, 'Credenciais inválidas.'))
    } finally {
      setLoading(false)
    }
  }

  const inputCls =
    'w-full pl-10 pr-3.5 py-3 rounded-xl border border-slate-200 bg-slate-50/60 text-sm text-slate-900 ' +
    'placeholder-slate-400 transition focus:outline-none focus:bg-white focus:border-brand ' +
    'focus:ring-4 focus:ring-brand/15'

  return (
    <div className="min-h-screen grid lg:grid-cols-[1.1fr_1fr] bg-white">
      {/* Painel de marca */}
      <aside
        className="relative hidden lg:flex flex-col justify-between overflow-hidden p-12 text-white"
        style={{ background: `linear-gradient(145deg, ${NAVY} 0%, #1B2F66 55%, ${BRAND_DARK} 100%)` }}
      >
        <div
          className="absolute -top-32 -left-24 h-96 w-96 rounded-full blur-3xl opacity-40 pointer-events-none"
          style={{ background: BLUE_LIGHT }}
        />
        <div
          className="absolute -bottom-40 -right-20 h-[28rem] w-[28rem] rounded-full blur-3xl opacity-30 pointer-events-none"
          style={{ background: '#7C3AED' }}
        />
        <img
          src={dispfarmWatermark}
          alt=""
          aria-hidden="true"
          className="pointer-events-none select-none absolute -right-16 top-1/2 -translate-y-1/2 h-[34rem] w-auto opacity-[0.06]"
        />

        <div className="relative flex items-center gap-3">
          <img src={dispfarmIcone} alt="DispFarm" className="h-11 w-auto drop-shadow-lg" />
          <div className="leading-tight">
            <p className="text-xl font-extrabold tracking-tight">
              DISP<span className="font-light">FARM</span>
            </p>
            <p className="text-[11px] tracking-[0.18em] uppercase text-white/55">Distribuidora Farmacêutica</p>
          </div>
        </div>

        <div className="relative max-w-md">
          <h2 className="text-4xl font-bold leading-tight tracking-tight">
            Controle total dos seus <span style={{ color: '#7DB9FF' }}>pedidos OL</span>.
          </h2>
          <p className="mt-4 text-white/65 leading-relaxed">
            Um painel único para acompanhar o ciclo completo do pedido, do recebimento ao retorno para a indústria.
          </p>

          <ul className="mt-10 space-y-5">
            {DESTAQUES.map(({ icon: Icon, titulo, texto }) => (
              <li key={titulo} className="flex gap-4">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/10 ring-1 ring-white/15 backdrop-blur">
                  <Icon size={18} className="text-[#7DB9FF]" />
                </span>
                <div>
                  <p className="font-semibold text-sm">{titulo}</p>
                  <p className="text-sm text-white/55">{texto}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-xs text-white/40">© {new Date().getFullYear()} DispFarm · PainelOL</p>
      </aside>

      {/* Formulário */}
      <main className="relative flex items-center justify-center px-6 py-12 bg-slate-50 lg:bg-white">
        <div className="w-full max-w-sm">
          {/* Marca (mobile) */}
          <div className="flex lg:hidden flex-col items-center mb-8">
            <img src={dispfarmIcone} alt="DispFarm" className="h-14 w-auto" />
            <p className="mt-3 text-lg font-extrabold tracking-tight" style={{ color: NAVY }}>
              DISP<span className="font-light">FARM</span>
            </p>
          </div>

          <h1 className="text-3xl font-bold tracking-tight" style={{ color: NAVY }}>
            Bem-vindo de volta
          </h1>
          <p className="mt-2 text-sm text-slate-500">Acesse o PainelOL com suas credenciais.</p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-5">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-slate-700 mb-1.5">
                E-mail
              </label>
              <div className="relative">
                <Mail size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="seu@email.com.br"
                  autoComplete="username"
                  required
                  autoFocus
                  className={inputCls}
                />
              </div>
            </div>

            <div>
              <label htmlFor="senha" className="block text-sm font-medium text-slate-700 mb-1.5">
                Senha
              </label>
              <div className="relative">
                <Lock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  id="senha"
                  type={showSenha ? 'text' : 'password'}
                  value={senha}
                  onChange={(e) => setSenha(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  required
                  className={`${inputCls} pr-11`}
                />
                <button
                  type="button"
                  onClick={() => setShowSenha((v) => !v)}
                  aria-label={showSenha ? 'Ocultar senha' : 'Mostrar senha'}
                  className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-1 text-slate-400 hover:text-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand"
                >
                  {showSenha ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {error && (
              <p
                role="alert"
                className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl px-3.5 py-2.5"
              >
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="group w-full py-3 px-4 rounded-xl text-sm font-semibold text-white shadow-lg shadow-brand/30 transition
                         hover:shadow-xl hover:shadow-brand/40 hover:-translate-y-px active:translate-y-0
                         disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:translate-y-0
                         focus:outline-none focus-visible:ring-4 focus-visible:ring-brand/30
                         flex items-center justify-center gap-2"
              style={{ background: `linear-gradient(135deg, ${BRAND} 0%, ${BRAND_DARK} 100%)` }}
            >
              {loading ? (
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : null}
              {loading ? 'Entrando…' : 'Entrar'}
              {!loading && <ArrowRight size={16} className="transition-transform group-hover:translate-x-0.5" />}
            </button>
          </form>

          <p className="mt-10 text-center text-xs text-slate-400">
            DispFarm — Sistema de Pedidos OL
          </p>
        </div>
      </main>
    </div>
  )
}
