/**
 * Main application component with routing.
 * Connects Customer Portal, Kitchen Owner Portal, and Admin Portal.
 */
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './hooks/useAuth';
import { RealtimeProvider } from './context/RealtimeContext';
import { CartProvider } from './context/CartContext';
import ProtectedRoute from './components/ProtectedRoute';

import CustomerLayout from './components/customer/CustomerLayout';
import KitchenLayout from './components/kitchen/KitchenLayout';
import AdminLayout from './components/admin/AdminLayout';
import RootRoute from './components/routing/RootRoute';

// Auth Pages
import Login from './pages/Login';
import Register from './pages/Register';
import VerifyEmail from './pages/VerifyEmail';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';
import Profile from './pages/Profile';

// Customer Pages
import CustomerHome from './pages/customer/Home';
import CustomerKitchens from './pages/customer/Kitchens';
import CustomerKitchenDetail from './pages/customer/KitchenDetail';
import CustomerMenu from './pages/customer/Menu';
import CustomerCart from './pages/customer/Cart';
import CustomerCheckout from './pages/customer/Checkout';
import CustomerOrders from './pages/customer/Orders';
import CustomerNotifications from './pages/customer/Notifications';

// Admin Pages
import AdminDashboard from './pages/admin/Dashboard';
import AdminUsers from './pages/admin/Users';
import AdminKitchenOwners from './pages/admin/KitchenOwners';
import AdminKitchens from './pages/admin/Kitchens';
import AdminMenu from './pages/admin/Menu';
import AdminOrders from './pages/admin/Orders';
import AdminPayments from './pages/admin/Payments';
import AdminInventory from './pages/admin/Inventory';
import AdminPromotions from './pages/admin/Promotions';
import AdminReviews from './pages/admin/Reviews';
import AdminWaste from './pages/admin/Waste';
import AdminDemandPredictions from './pages/admin/DemandPredictions';
import AdminAnalytics from './pages/admin/Analytics';
import AdminAuditLogs from './pages/admin/AuditLogs';
import AdminProfile from './pages/admin/Profile';
import AdminNotifications from './pages/admin/Notifications';
import AdminSettings from './pages/admin/Settings';

// Kitchen Owner Pages
import KitchenDashboard from './pages/kitchen/Dashboard';
import KitchenOrders from './pages/kitchen/Orders';
import KitchenMenu from './pages/kitchen/Menu';
import KitchenIngredients from './pages/kitchen/Ingredients';
import KitchenInventory from './pages/kitchen/Inventory';
import KitchenRestocking from './pages/kitchen/Restocking';
import KitchenWaste from './pages/kitchen/Waste';
import KitchenDemandForecast from './pages/kitchen/DemandForecast';
import KitchenNotifications from './pages/kitchen/Notifications';
import KitchenSettings from './pages/kitchen/Settings';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <RealtimeProvider>
          <CartProvider>
            <Routes>
            {/* Customer Portal Public & Protected Routes inside CustomerLayout */}
            <Route element={<CustomerLayout />}>
              <Route path="/" element={<RootRoute />} />
              <Route path="/customer" element={<Navigate to="/" replace />} />
              <Route path="/customer/*" element={<Navigate to="/" replace />} />
              <Route path="/kitchens" element={<CustomerKitchens />} />
              <Route path="/kitchens/:id" element={<CustomerKitchenDetail />} />
              <Route path="/menu" element={<CustomerMenu />} />
              <Route path="/cart" element={<CustomerCart />} />
              <Route
                path="/checkout"
                element={
                  <ProtectedRoute allowedRoles={['CUSTOMER']}>
                    <CustomerCheckout />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/orders"
                element={
                  <ProtectedRoute allowedRoles={['CUSTOMER']}>
                    <CustomerOrders />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/notifications"
                element={
                  <ProtectedRoute allowedRoles={['CUSTOMER']}>
                    <CustomerNotifications />
                  </ProtectedRoute>
                }
              />
            </Route>

            {/* Auth Public routes */}
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/verify-email" element={<VerifyEmail />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/reset-password" element={<ResetPassword />} />

            {/* Profile (all authenticated roles) */}
            <Route
              path="/profile"
              element={
                <ProtectedRoute>
                  <Profile />
                </ProtectedRoute>
              }
            />

            {/* Kitchen Owner routes - KITCHEN_OWNER role only */}
            <Route
              path="/kitchen"
              element={
                <ProtectedRoute allowedRoles={['KITCHEN_OWNER']}>
                  <KitchenLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/kitchen/dashboard" replace />} />
              <Route path="dashboard" element={<KitchenDashboard />} />
              <Route path="orders" element={<KitchenOrders />} />
              <Route path="menu" element={<KitchenMenu />} />
              <Route path="ingredients" element={<KitchenIngredients />} />
              <Route path="inventory" element={<KitchenInventory />} />
              <Route path="restocking" element={<KitchenRestocking />} />
              <Route path="waste" element={<KitchenWaste />} />
              <Route path="forecast" element={<KitchenDemandForecast />} />
              <Route path="notifications" element={<KitchenNotifications />} />
              <Route path="settings" element={<KitchenSettings />} />
            </Route>

            {/* Kitchen Owner alias redirects */}
            <Route path="/kitchen-owner" element={<Navigate to="/kitchen/dashboard" replace />} />
            <Route path="/kitchen-owner/*" element={<Navigate to="/kitchen/dashboard" replace />} />

            {/* Admin routes - ADMIN role only */}
            <Route
              path="/admin"
              element={
                <ProtectedRoute allowedRoles={['ADMIN']}>
                  <AdminLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/admin/dashboard" replace />} />
              <Route path="dashboard" element={<AdminDashboard />} />
              <Route path="users" element={<AdminUsers />} />
              <Route path="kitchen-owners" element={<AdminKitchenOwners />} />
              <Route path="kitchens" element={<AdminKitchens />} />
              <Route path="menu" element={<AdminMenu />} />
              <Route path="orders" element={<AdminOrders />} />
              <Route path="payments" element={<AdminPayments />} />
              <Route path="inventory" element={<AdminInventory />} />
              <Route path="promotions" element={<AdminPromotions />} />
              <Route path="reviews" element={<AdminReviews />} />
              <Route path="waste" element={<AdminWaste />} />
              <Route path="demand-predictions" element={<AdminDemandPredictions />} />
              <Route path="analytics" element={<AdminAnalytics />} />
              <Route path="audit-logs" element={<AdminAuditLogs />} />
              <Route path="notifications" element={<AdminNotifications />} />
              <Route path="settings" element={<AdminSettings />} />
              <Route path="profile" element={<AdminProfile />} />
            </Route>

            {/* Catch-all redirect */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </CartProvider>
      </RealtimeProvider>
    </AuthProvider>
    </BrowserRouter>
  );
}
