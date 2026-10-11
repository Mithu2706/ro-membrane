import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import { PublicLayout } from "./components/Layout";
import { PageLoader } from "./components/ui";
import Landing from "./pages/Landing";
import Assess from "./pages/Assess";
import Results from "./pages/Results";
import NotFound from "./pages/NotFound";

const AdminApp = lazy(() => import("./admin/AdminApp"));

export default function App() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route path="/" element={<Landing />} />
        <Route path="/assess" element={<Assess />} />
        <Route path="/results/:token" element={<Results />} />
        <Route path="*" element={<NotFound />} />
      </Route>
      <Route
        path="/admin/*"
        element={
          <Suspense fallback={<PageLoader label="Loading console" />}>
            <AdminApp />
          </Suspense>
        }
      />
    </Routes>
  );
}
