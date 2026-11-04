import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, ShoppingCart, Truck, AlertTriangle, FileText,
  Users, Activity, LogOut, Factory, Info, History, SlidersHorizontal,
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { perfilEmAlgum } from '../../lib/perfil'
import dispfarmLogo  from '../../assets/DISPFARM ICONE.png'

interface NavItem {
  to: string
  icon: React.ReactNode
  label: string
  /** Restringe o item aos perfis listados (comparação tolerante — ver
   *  lib/perfil.ts). Omitido = visível pra qualquer perfil autenticado. */
  perfis?: string[]
}

const NAV: NavItem[] = [
  { to: '/dashboard',   icon: <LayoutDashboard size={17} />, label: 'Dashboard' },
  { to: '/pedidos/confeccao',     icon: <ShoppingCart size={17} />, label: 'Triagem' },
  { to: '/pedidos/rastreamento',  icon: <Truck size={17} />,        label: 'Rastreamento' },
  { to: '/pedidos/historico',      icon: <History size={17} />,      label: 'Histórico' },
  { to: '/ocorrencias', icon: <AlertTriangle size={17} />,   label: 'Ocorrências' },
  { to: '/arquivos',    icon: <FileText size={17} />,        label: 'Arquivos' },
  { to: '/usuarios',    icon: <Users size={17} />,           label: 'Usuários', perfis: ['Administrador'] },
  { to: '/servicos',    icon: <Activity size={17} />,        label: 'Serviços', perfis: ['Administrador'] },
  { to: '/industrias',  icon: <Factory size={17} />,         label: 'Indústrias', perfis: ['Administrador'] },
  { to: '/parametrizacao', icon: <SlidersHorizontal size={17} />, label: 'Parametrização', perfis: ['Administrador', 'Gerente Comercial'] },
  { to: '/info',        icon: <Info size={17} />,             label: 'Info' },
]


export default function Sidebar() {
  const { user, logout } = useAuth()

  return (
    <aside
      className="fixed inset-y-0 left-0 w-60 flex flex-col bg-navy"
    >
      {/* Logo */}
      <div
        className="px-5 py-4"
        style={{
          borderBottom: '1px solid rgba(255,255,255,0.07)',
          background: 'linear-gradient(180deg, rgba(33,150,243,0.08) 0%, transparent 100%)',
        }}
      >
        <div className="flex items-center gap-3">
          <img src={dispfarmLogo} alt="DispFarm" className="h-6 w-auto" />
          <div>
            <p className="text-white font-bold text-sm leading-none tracking-tight">
              PainelOL
            </p>
            <p className="text-xs mt-1" style={{ color: 'rgba(255,255,255,0.35)' }}>
              DispFarm
            </p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {NAV.filter((item) => !item.perfis || perfilEmAlgum(user?.perfil, item.perfis)).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              [
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'text-[#2196F3]'
                  : 'text-white/45 hover:bg-white/5 hover:text-white/75',
              ].join(' ')
            }
            style={({ isActive }) =>
              isActive ? { backgroundColor: 'rgba(33,150,243,0.14)' } : undefined
            }
          >
            {item.icon}
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* User */}
      <div className="px-3 py-4" style={{ borderTop: '1px solid rgba(255,255,255,0.07)' }}>
        <div className="flex items-center gap-3 px-3 py-2 mb-1">
          <div
            className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0"
            style={{ backgroundColor: 'rgba(33,150,243,0.18)' }}
          >
            <span className="text-xs font-bold" style={{ color: '#2196F3' }}>
              {user?.nome?.[0]?.toUpperCase() ?? '?'}
            </span>
          </div>
          <div className="min-w-0">
            <p className="text-xs font-medium truncate" style={{ color: 'rgba(255,255,255,0.78)' }}>
              {user?.nome}
            </p>
            <p className="text-xs truncate" style={{ color: 'rgba(255,255,255,0.33)' }}>
              {user?.perfil}
            </p>
          </div>
        </div>
        <button
          onClick={logout}
          className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm font-medium transition-colors text-white/45 hover:bg-white/5 hover:text-white/75"
        >
          <LogOut size={16} />
          Sair
        </button>
      </div>
    </aside>
  )
}
