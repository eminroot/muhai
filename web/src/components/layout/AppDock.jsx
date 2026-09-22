import { useLocation, useNavigate } from 'react-router-dom'
import {
  Boxes,
  LayoutGrid,
  Landmark,
  Moon,
  ReceiptText,
  Settings,
  Sparkles,
  Sun,
  Users,
} from 'lucide-react'
import { Dock, DockIcon, DockItem, DockLabel } from './Dock.jsx'
import { useLang } from '../../i18n/LanguageContext.jsx'
import { useData } from '../../context/DataContext.jsx'
import { useTheme } from '../../context/ThemeContext.jsx'

/**
 * A count riding on a dock tile, the way an OS dock marks unread work.
 *
 * DockItem clones its children with `width` and `isHovered` so the icon can
 * track the tile; this swallows both rather than leaking them onto the span.
 */
function DockBadge({ children, width, isHovered, ...rest }) {
  return (
    <span className="dock-badge num" {...rest}>
      {children}
    </span>
  )
}

export default function AppDock() {
  const { t } = useLang()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { invoices, products } = useData()
  const { theme, toggle } = useTheme()

  // Badges count real, actionable things — unpaid invoices and low stock.
  const unpaid = invoices.filter((i) => i.status !== 'paid').length
  const lowStock = products.filter((p) => (p.stock ?? 0) <= (p.minStock ?? 0)).length

  const destinations = [
    { to: '/app', id: 'dashboard', icon: LayoutGrid, end: true },
    { to: '/app/invoices', id: 'invoices', icon: ReceiptText, badge: unpaid },
    { to: '/app/tax', id: 'tax', icon: Landmark },
    { to: '/app/inventory', id: 'inventory', icon: Boxes, badge: lowStock },
    { to: '/app/payroll', id: 'payroll', icon: Users },
    { to: '/app/assistant', id: 'assistant', icon: Sparkles },
  ]

  const isLive = (to, end) => (end ? pathname === to : pathname.startsWith(to))

  // Modified clicks stay with the browser, so a destination can still be
  // opened in a new tab.
  const follow = (to) => (event) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return
    event.preventDefault()
    navigate(to)
  }

  return (
    <Dock>
      {destinations.map(({ to, id, icon: Icon, end, badge }) => (
        <DockItem key={to} href={to} onClick={follow(to)} active={isLive(to, end)}>
          <DockLabel>{t(`dock.${id}`)}</DockLabel>
          <DockIcon>
            <Icon strokeWidth={1.75} />
          </DockIcon>
          {badge ? <DockBadge>{badge > 99 ? '99+' : badge}</DockBadge> : null}
        </DockItem>
      ))}

      <span className="dock-sep" aria-hidden="true" />

      <DockItem
        href="/app/settings"
        onClick={follow('/app/settings')}
        active={isLive('/app/settings')}
      >
        <DockLabel>{t('dock.settings')}</DockLabel>
        <DockIcon>
          <Settings strokeWidth={1.75} />
        </DockIcon>
      </DockItem>

      <DockItem onClick={toggle} aria-label={t(theme === 'dark' ? 'common.lightMode' : 'common.darkMode')}>
        <DockLabel>{t(theme === 'dark' ? 'common.lightMode' : 'common.darkMode')}</DockLabel>
        <DockIcon>{theme === 'dark' ? <Sun strokeWidth={1.75} /> : <Moon strokeWidth={1.75} />}</DockIcon>
      </DockItem>
    </Dock>
  )
}
