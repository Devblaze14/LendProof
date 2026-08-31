import { Navigate, Route, Routes } from "react-router-dom";
import Home from "./pages/Home";
import Login from "./pages/Login";
import OperatorDashboard from "./pages/OperatorDashboard";
import ReviewerDashboard from "./pages/ReviewerDashboard";
import ConsumerDashboard from "./pages/ConsumerDashboard";
import { getSession, Role } from "./api/client";

function RequireRole({ role, children }: { role: Role; children: JSX.Element }) {
  const session = getSession();
  if (!session) return <Navigate to="/login" replace />;
  if (session.role !== role) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      {/* Operator routes */}
      <Route path="/operator" element={<RequireRole role="operator"><OperatorDashboard /></RequireRole>} />
      <Route path="/operator/*" element={<RequireRole role="operator"><OperatorDashboard /></RequireRole>} />
      {/* Reviewer routes */}
      <Route path="/reviewer" element={<RequireRole role="reviewer"><ReviewerDashboard /></RequireRole>} />
      <Route path="/reviewer/*" element={<RequireRole role="reviewer"><ReviewerDashboard /></RequireRole>} />
      {/* Consumer routes */}
      <Route path="/consumer" element={<RequireRole role="consumer"><ConsumerDashboard /></RequireRole>} />
      <Route path="/consumer/*" element={<RequireRole role="consumer"><ConsumerDashboard /></RequireRole>} />
    </Routes>
  );
}
