import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { Loading } from './components/ui'
import { useAuth } from './context/AuthContext'
import { homePath } from './lib/permissions'
import AdminDashboardPage from './pages/AdminDashboardPage'
import DashboardPage from './pages/DashboardPage'
import ExpensesPage from './pages/ExpensesPage'
import ForgotPasswordPage from './pages/ForgotPasswordPage'
import LoginPage from './pages/LoginPage'
import NewSalePage from './pages/NewSalePage'
import ProductionPage from './pages/ProductionPage'
import ProfilePage from './pages/ProfilePage'
import ProductsPage from './pages/ProductsPage'
import RegisterPage from './pages/RegisterPage'
import ReportsPage from './pages/ReportsPage'
import SalesPage from './pages/SalesPage'
import SettingsPage from './pages/SettingsPage'
import SubscriptionPage from './pages/SubscriptionPage'

// Pages that need a logged-in user
function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <Loading />
  if (!user) return <Navigate to="/login" replace />
  return children
}

// Pages only the business owner may see
function OwnerOnly({ children }) {
  const { user, isOwner } = useAuth()
  return isOwner ? children : <Navigate to={homePath(user)} replace />
}

// Pages a staff member may open only if the owner allowed it (see Settings -> Staff)
function Allowed({ permission, children }) {
  const { user, can } = useAuth()
  return can(permission) ? children : <Navigate to={homePath(user)} replace />
}

// Shop pages need a shop. Admins who have none go to the admin dashboard.
function RequireBusiness() {
  const { user, isAdmin } = useAuth()
  if (user.business) return <Outlet />
  return <Navigate to={isAdmin ? '/manage' : '/login'} replace />
}

// The admin dashboard, only for platform admins
function AdminOnly({ children }) {
  const { isAdmin } = useAuth()
  return isAdmin ? children : <Navigate to="/" replace />
}

// Login and register pages: skip them if already logged in
function GuestOnly({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <Loading />
  return user ? <Navigate to="/" replace /> : children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<GuestOnly><LoginPage /></GuestOnly>} />
      <Route path="/register" element={<GuestOnly><RegisterPage /></GuestOnly>} />
      <Route path="/forgot-password" element={<GuestOnly><ForgotPasswordPage /></GuestOnly>} />

      <Route element={<RequireAuth><Layout /></RequireAuth>}>
        <Route path="manage" element={<AdminOnly><AdminDashboardPage /></AdminOnly>} />
        <Route path="profile" element={<ProfilePage />} />
        <Route element={<RequireBusiness />}>
          <Route index element={<Allowed permission="reports"><DashboardPage /></Allowed>} />
          <Route path="sell" element={<Allowed permission="sales"><NewSalePage /></Allowed>} />
          <Route path="sales" element={<SalesPage />} />
          <Route path="products" element={<ProductsPage />} />
          <Route path="expenses" element={<Allowed permission="expenses"><ExpensesPage /></Allowed>} />
          <Route path="production" element={<Allowed permission="production"><ProductionPage /></Allowed>} />
          <Route path="reports" element={<Allowed permission="reports"><ReportsPage /></Allowed>} />
          <Route path="subscription" element={<SubscriptionPage />} />
          <Route path="settings" element={<OwnerOnly><SettingsPage /></OwnerOnly>} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
