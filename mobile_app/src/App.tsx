import React, { Suspense, lazy, useEffect, useRef } from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import { UiProvider } from '@/contexts/UiContext';
import { CartProvider } from '@/contexts/CartContext';
import { Toaster } from '@/components/ui/toaster';
import { GlobalAuthLoader } from '@/components/auth/GlobalAuthLoader';
import { NotificationRuntime } from '@/components/notifications/NotificationRuntime';
import { useGuestStore } from '@/stores/guestStore';
import ScrollToTop from "@/components/routing/ScrollToTop";
import { RouteAnalytics } from '@/components/analytics/RouteAnalytics';
import { analytics } from '@/lib/analytics';
import { startTrace, stopTrace } from '@/lib/performance';
import { useFirstTimeAuthedRedirect } from '@/hooks/useFirstTimeAuthedRedirect';

const queryClient = new QueryClient();
const WelcomePage = lazy(() =>
  import('@/pages/Welcome').then((module) => ({ default: module.Welcome }))
);
const AuthPage = lazy(() =>
  import('@/pages/Auth').then((module) => ({ default: module.Auth }))
);
const ResetPasswordPage = lazy(() =>
  import('@/pages/ResetPassword').then((module) => ({
    default: module.ResetPassword,
  }))
);
const AddItemPage = lazy(() =>
  import('@/pages/AddItem').then((module) => ({ default: module.AddItem }))
);
const ExpiringSoonPage = lazy(() =>
  import('@/pages/ExpiringSoon').then((module) => ({
    default: module.ExpiringSoon,
  }))
);
const DealSearchPage = lazy(() =>
  import('@/pages/DealSearch').then((module) => ({
    default: module.DealSearch,
  }))
);
const CartFinderPage = lazy(() =>
  import('@/pages/CartFinder').then((module) => ({
    default: module.CartFinder,
  }))
);
const CartPageRoute = lazy(() =>
  import('@/pages/CartPage').then((module) => ({ default: module.CartPage }))
);
const HouseholdsPage = lazy(() =>
  import('@/components/home/households/households').then((module) => ({
    default: module.Households,
  }))
);
const SettingsPage = lazy(() =>
  import('@/components/home/settings/Settings').then((module) => ({
    default: module.Settings,
  }))
);
const OnboardingZipCodePage = lazy(() =>
  import('@/pages/OnboardingZipCode').then((module) => ({
    default: module.OnboardingZipCode,
  }))
);
const OnboardingChooseStoresPage = lazy(() =>
  import('@/pages/OnboardingChooseStores').then((module) => ({
    default: module.OnboardingChooseStores,
  }))
);
const OnboardingSavingsPreviewPage = lazy(() =>
  import('@/pages/OnboardingSavingsPreview').then((module) => ({
    default: module.OnboardingSavingsPreview,
  }))
);
const SavingsOnboardingPage = lazy(() =>
  import('@/pages/SavingsOnboarding').then((module) => ({
    default: module.SavingsOnboarding,
  }))
);
const PantryTrackerPage = lazy(() =>
  import('@/pages/pantry-tracker').then((module) => ({
    default: module.PantryTracker,
  }))
);
const AccountPage = lazy(() =>
  import('@/pages/Account').then((module) => ({ default: module.Account }))
);
const PersonalInfoPage = lazy(() =>
  import('@/pages/PersonalInfo').then((module) => ({
    default: module.PersonalInfo,
  }))
);
const PreferredRetailersPage = lazy(() =>
  import('@/pages/PreferredRetailers').then((module) => ({
    default: module.PreferredRetailers,
  }))
);
const PreferredBrandsPage = lazy(() =>
  import('@/pages/PreferredBrands').then((module) => ({
    default: module.PreferredBrands,
  }))
);
const NotificationsPage = lazy(() =>
  import('@/pages/Notifications').then((module) => ({
    default: module.Notifications,
  }))
);
const PrivacyPolicyPage = lazy(() =>
  import('@/pages/PrivacyPolicy').then((module) => ({
    default: module.PrivacyPolicy,
  }))
);
const TermsOfServicePage = lazy(() =>
  import('@/pages/TermsOfService').then((module) => ({
    default: module.TermsOfService,
  }))
);
const DealsPage = lazy(() =>
  import('@/pages/Deals').then((module) => ({ default: module.Deals }))
);
const DealsSectionPage = lazy(() =>
  import('@/pages/DealsSection').then((module) => ({
    default: module.DealsSection,
  }))
);
const DealDetailsPage = lazy(() =>
  import('@/pages/deals/DealDetails').then((module) => ({
    default: module.DealDetails,
  }))
);
const FeedbackPage = lazy(() =>
  import('@/pages/Feedback').then((module) => ({ default: module.Feedback }))
);
const FeedbackThankYouPage = lazy(() =>
  import('@/pages/FeedbackThankYou').then((module) => ({
    default: module.FeedbackThankYou,
  }))
);
const EditPantryItemPage = lazy(() =>
  import('@/pages/EditPantryItem').then((module) => ({
    default: module.EditPantryItem,
  }))
);
const NotFoundPage = lazy(() =>
  import('@/pages/NotFound').then((module) => ({ default: module.default }))
);

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const { isGuest } = useGuestStore();

  if (loading) {
    return <GlobalAuthLoader />;
  }

  if (!user && !isGuest) {
    return <Navigate to="/welcome" replace />;
  }

  return <>{children}</>;
}

function WelcomeRoute() {
  const status = useFirstTimeAuthedRedirect();
  if (status === "loading") return <GlobalAuthLoader />;
  if (status === "home") return <Navigate to="/home" replace />;
  if (status === "onboarding") return <Navigate to="/onboarding" replace />;
  return <WelcomePage />;
}

function RootRoute() {
  const status = useFirstTimeAuthedRedirect();
  if (status === "loading") return <GlobalAuthLoader />;
  if (status === "home") return <Navigate to="/home" replace />;
  if (status === "onboarding") return <Navigate to="/onboarding" replace />;
  return <Navigate to="/welcome" replace />;
}

function StartupTelemetry() {
  const { loading } = useAuth();
  const startupTraceStarted = useRef(false);
  const startupTraceStopped = useRef(false);

  useEffect(() => {
    analytics.init();
  }, []);

  useEffect(() => {
    if (startupTraceStarted.current) {
      return;
    }

    startupTraceStarted.current = true;
    void startTrace("app_startup_trace", { surface: "bootstrap" });

    return () => {
      if (startupTraceStopped.current) {
        return;
      }

      startupTraceStopped.current = true;
      void stopTrace("app_startup_trace");
    };
  }, []);

  useEffect(() => {
    if (loading || startupTraceStopped.current) {
      return;
    }

    startupTraceStopped.current = true;
    void stopTrace("app_startup_trace");
  }, [loading]);

  return null;
}

function AppRoutes() {
  const { loading } = useAuth();

  if (loading) {
    return <GlobalAuthLoader />;
  }

  return (
    <Suspense fallback={<GlobalAuthLoader />}>
      <Routes>
      {/* Public / auth routes */}
      <Route path="/welcome" element={<WelcomeRoute />} />
      <Route path="/auth" element={<AuthPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route
        path="/pantry-tracker/edit/:id"
        element={
          <ProtectedRoute>
            <EditPantryItemPage />
          </ProtectedRoute>
        }
      />

      {/* NEW: /home now shows the Cart Finder experience */}
      <Route
        path="/home"
        element={
          <ProtectedRoute>
            <CartFinderPage />
          </ProtectedRoute>
        }
      />

      {/* NEW: Old home screen is now "Pantry Tracker" */}
      <Route
        path="/pantry-tracker"
        element={
          <ProtectedRoute>
            <PantryTrackerPage />
          </ProtectedRoute>
        }
      />

      {/* Root route sends signed-in users directly into the app */}
      <Route path="/" element={<RootRoute />} />

      {/* New savings onboarding flow (post-signup / guest) */}
      <Route path="/onboarding" element={<SavingsOnboardingPage />} />

      {/* Onboarding routes (unchanged) */}
      <Route path="/onboarding/zipcode" element={<OnboardingZipCodePage />} />
      <Route
        path="/onboarding/choose-stores"
        element={<OnboardingChooseStoresPage />}
      />
      <Route
        path="/onboarding/savings-preview"
        element={<OnboardingSavingsPreviewPage />}
      />

      {/* Other app routes (unchanged behavior) */}
      <Route
        path="/add-item"
        element={
          <ProtectedRoute>
            <AddItemPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/pantry-tracker/households"
        element={
          <ProtectedRoute>
            <HouseholdsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/expiring-soon"
        element={
          <ProtectedRoute>
            <ExpiringSoonPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/pantry-tracker/settings"
        element={
          <ProtectedRoute>
            <SettingsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/home/households"
        element={<Navigate to="/pantry-tracker/households" replace />}
      />
      <Route
        path="/home/settings"
        element={<Navigate to="/pantry-tracker/settings" replace />}
      />
      <Route path="/deal-search" element={<DealSearchPage />} />
      <Route
        path="/cart-finder"
        element={
          <ProtectedRoute>
            <CartFinderPage />
          </ProtectedRoute>
        }
      />
      <Route path="/cart" element={<CartPageRoute />} />
      <Route path="/deals" element={<DealsPage />} />
      <Route path="/deals/:matchKey" element={<DealDetailsPage />} />
      <Route path="/deals/section" element={<DealsSectionPage />} />
      <Route
        path="/account"
        element={
          <ProtectedRoute>
            <AccountPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/account/personal-info"
        element={
          <ProtectedRoute>
            <PersonalInfoPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/account/preferred-retailers"
        element={
          <ProtectedRoute>
            <PreferredRetailersPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/account/preferred-brands"
        element={
          <ProtectedRoute>
            <PreferredBrandsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/account/notifications"
        element={
          <ProtectedRoute>
            <NotificationsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/account/privacy-policy"
        element={
          <ProtectedRoute>
            <PrivacyPolicyPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/account/terms-of-service"
        element={
          <ProtectedRoute>
            <TermsOfServicePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/TermsofService"
        element={<TermsOfServicePage />}
      />
      <Route
        path="/feedback"
        element={
          <ProtectedRoute>
            <FeedbackPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/feedback/thank-you"
        element={
          <ProtectedRoute>
            <FeedbackThankYouPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <StartupTelemetry />
        <UiProvider>
          <CartProvider>
            <Router>
              <ScrollToTop />
              <RouteAnalytics />
              <NotificationRuntime />
              <div className="min-h-[100dvh] bg-gradient-background">
                <AppRoutes />
                <Toaster />
              </div>
            </Router>
          </CartProvider>
        </UiProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
