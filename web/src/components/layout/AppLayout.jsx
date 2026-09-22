import { Outlet, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import SideRail from './SideRail.jsx'
import Topbar from './Topbar.jsx'
import ChatWidget from '../chatbot/ChatWidget.jsx'
import { DataProvider } from '../../context/DataContext.jsx'

export default function AppLayout() {
  const location = useLocation()

  return (
    <DataProvider>
      <div className="app-shell">
        {/* Navigation moved off the bottom dock and onto a left rail. Two
            navigation systems on one screen is one too many, so the dock is
            gone rather than doubled up — `AppDock.jsx` is untouched if it
            should come back. */}
        <SideRail />

        <div className="main-col">
          <Topbar />
          <AnimatePresence mode="wait">
            <motion.main
              key={location.pathname}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.18, ease: [0.22, 0.8, 0.3, 1] }}
            >
              <Outlet />
            </motion.main>
          </AnimatePresence>
        </div>

        <ChatWidget />
      </div>
    </DataProvider>
  )
}
