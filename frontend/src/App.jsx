import { Suspense, lazy } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './auth/AuthContext.jsx';
import AuthPage from './pages/AuthPage.jsx';
import Dashboard from './pages/Dashboard.jsx';
import HealthProfilePage from './pages/HealthProfilePage.jsx';
import ProductEntryPage from './pages/ProductEntryPage.jsx';
import ProductSearchPage from './pages/ProductSearchPage.jsx';
import ProductHistoryPage from './pages/ProductHistoryPage.jsx';
import ProductWatchlistPage from './pages/ProductWatchlistPage.jsx';

const ProductScanPage = lazy(() => import('./pages/ProductScanPage.jsx'));
const ProductDetailPage = lazy(() => import('./pages/ProductDetailPage.jsx'));
const IngredientAnalysisPage = lazy(() => import('./pages/IngredientAnalysisPage.jsx'));
const IngredientHistoryComparisonPage = lazy(
  () => import('./pages/IngredientHistoryComparisonPage.jsx'),
);
const ProductRecommendationsPage = lazy(
  () => import('./pages/ProductRecommendationsPage.jsx'),
);
const ProductComparisonPage = lazy(() => import('./pages/ProductComparisonPage.jsx'));
const FoodClaimsPage = lazy(() => import('./pages/FoodClaimsPage.jsx'));

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return <main className="app-loading">Loading your account...</main>;
  }
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage mode="login" />} />
      <Route path="/signup" element={<AuthPage mode="signup" />} />
      <Route
        path="/profile/setup"
        element={
          <ProtectedRoute>
            <HealthProfilePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/products"
        element={
          <ProtectedRoute>
            <ProductSearchPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/products/new"
        element={
          <ProtectedRoute>
            <Suspense fallback={<main className="app-loading">Preparing product scanner...</main>}>
              <ProductScanPage />
            </Suspense>
          </ProtectedRoute>
        }
      />
      <Route
        path="/products/manual"
        element={
          <ProtectedRoute>
            <ProductEntryPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/history"
        element={
          <ProtectedRoute>
            <ProductHistoryPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/watchlist"
        element={
          <ProtectedRoute>
            <ProductWatchlistPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/products/compare"
        element={
          <ProtectedRoute>
            <Suspense fallback={<main className="app-loading">Preparing product comparison...</main>}>
              <ProductComparisonPage />
            </Suspense>
          </ProtectedRoute>
        }
      />
      <Route
        path="/ingredient-history"
        element={
          <ProtectedRoute>
            <Suspense fallback={<main className="app-loading">Loading ingredient history...</main>}>
              <IngredientHistoryComparisonPage />
            </Suspense>
          </ProtectedRoute>
        }
      />
      <Route
        path="/products/:productId/ingredients"
        element={
          <ProtectedRoute>
            <Suspense fallback={<main className="app-loading">Preparing ingredient analysis...</main>}>
              <IngredientAnalysisPage />
            </Suspense>
          </ProtectedRoute>
        }
      />
      <Route
        path="/products/:productId/claims"
        element={
          <ProtectedRoute>
            <Suspense fallback={<main className="app-loading">Preparing packaging claim analysis...</main>}>
              <FoodClaimsPage />
            </Suspense>
          </ProtectedRoute>
        }
      />
      <Route
        path="/products/:productId/recommendations"
        element={
          <ProtectedRoute>
            <Suspense fallback={<main className="app-loading">Finding comparable products...</main>}>
              <ProductRecommendationsPage />
            </Suspense>
          </ProtectedRoute>
        }
      />
      <Route
        path="/products/:productId"
        element={
          <ProtectedRoute>
            <Suspense fallback={<main className="app-loading">Loading product analysis...</main>}>
              <ProductDetailPage />
            </Suspense>
          </ProtectedRoute>
        }
      />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
