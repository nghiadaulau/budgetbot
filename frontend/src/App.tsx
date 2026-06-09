import { Suspense, lazy } from "react";
import { Routes, Route } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { Skeleton } from "@/components/ui/skeleton";
import { Brand } from "@/components/layout/Brand";
import { useAuth } from "@/context/auth";

const Dashboard = lazy(() => import("@/pages/Dashboard"));
const Transactions = lazy(() => import("@/pages/Transactions"));
const UploadCsv = lazy(() => import("@/pages/UploadCsv"));
const UploadPdf = lazy(() => import("@/pages/UploadPdf"));
const Insights = lazy(() => import("@/pages/Insights"));
const Settings = lazy(() => import("@/pages/Settings"));
const AuthPage = lazy(() => import("@/pages/AuthPage"));

function PageFallback() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

/** Brand splash while the session restores (avoids an auth-page flash). */
function AuthSplash() {
  return (
    <div className="grid min-h-dvh place-items-center bg-background">
      <div className="animate-pulse">
        <Brand />
      </div>
    </div>
  );
}

export default function App() {
  const { status } = useAuth();

  if (status === "loading") return <AuthSplash />;

  if (status === "unauthed") {
    return (
      <Suspense fallback={<AuthSplash />}>
        <AuthPage />
      </Suspense>
    );
  }

  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route
          index
          element={
            <Suspense fallback={<PageFallback />}>
              <Dashboard />
            </Suspense>
          }
        />
        <Route
          path="transactions"
          element={
            <Suspense fallback={<PageFallback />}>
              <Transactions />
            </Suspense>
          }
        />
        <Route
          path="upload"
          element={
            <Suspense fallback={<PageFallback />}>
              <UploadCsv />
            </Suspense>
          }
        />
        <Route
          path="receipt"
          element={
            <Suspense fallback={<PageFallback />}>
              <UploadPdf />
            </Suspense>
          }
        />
        <Route
          path="insights"
          element={
            <Suspense fallback={<PageFallback />}>
              <Insights />
            </Suspense>
          }
        />
        <Route
          path="settings"
          element={
            <Suspense fallback={<PageFallback />}>
              <Settings />
            </Suspense>
          }
        />
      </Route>
    </Routes>
  );
}
