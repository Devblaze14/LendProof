import { useState, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, saveSession, ApiError } from "../api/client";
import { Icon } from "../components/DashboardShell";

const ROLE_HOME: Record<string, string> = {
  operator: "/operator", reviewer: "/reviewer", consumer: "/consumer",
};

const DEMO_ACCOUNTS = [
  { label: "Operator", email: "operator@testmail.dev", icon: "upload_file", desc: "Upload & manage loan files" },
  { label: "Reviewer", email: "reviewer@testmail.dev", icon: "gavel", desc: "Review exceptions with AI" },
  { label: "Consumer", email: "consumer@testmail.dev", icon: "verified", desc: "View verified records" },
];

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [guestLoading, setGuestLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [selectedRole, setSelectedRole] = useState("operator");
  const formRef = useRef<HTMLFormElement>(null);
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await api.login(email, password);
      saveSession({ accessToken: res.access_token, role: res.role, name: res.name });
      navigate(ROLE_HOME[res.role] ?? "/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not sign in. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  }

  async function continueAsGuest() {
    setError(null);
    setGuestLoading(true);
    try {
      const res = await api.guest();
      saveSession({ accessToken: res.access_token, role: res.role, name: "Guest viewer" });
      navigate("/consumer");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not connect to the API. Start the backend and try again.");
    } finally {
      setGuestLoading(false);
    }
  }

  function selectDemo(account: typeof DEMO_ACCOUNTS[0]) {
    setSelectedRole(account.label.toLowerCase());
    setEmail(account.email);
    setPassword("DemoPass123!");
    setError(null);
  }

  return (
    <div className="min-h-screen bg-mesh flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background Orbs */}
      <div className="absolute top-1/4 left-1/4 w-[500px] h-[500px] rounded-full bg-accent/5 blur-[120px] animate-float" />
      <div className="absolute bottom-1/4 right-1/4 w-[400px] h-[400px] rounded-full bg-emerald-500/5 blur-[100px] animate-float" style={{ animationDelay: "1.5s" }} />
      <div className="absolute top-1/2 left-1/2 w-[300px] h-[300px] rounded-full bg-amber-500/3 blur-[80px]" />

      <div className="relative z-10 w-full max-w-[480px] animate-fade-in-up">
        <Link to="/" className="inline-flex items-center gap-2 text-xs text-muted hover:text-white transition-colors mb-7">
          <Icon name="arrow_back" size={15} /> Back to overview
        </Link>
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-accent to-accent-dark mb-4 animate-pulse-glow">
            <Icon name="link" className="text-white" size={28} />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">LendProof</h1>
          <p className="text-sm text-subtle mt-1">Loan Data Verification Copilot</p>
        </div>

        {/* Login Card */}
        <div className="glass-card p-8">
          <h2 className="text-lg font-semibold text-white mb-1">Welcome back</h2>
          <p className="text-sm text-subtle mb-6">Sign in for role-based tools, or continue as a read-only guest.</p>

          <div className="role-tabs" aria-label="Choose workspace">
            {DEMO_ACCOUNTS.map((account) => (
              <button key={account.label} type="button" onClick={() => selectDemo(account)} className={selectedRole === account.label.toLowerCase() ? "role-tab active" : "role-tab"}>
                <Icon name={account.icon} size={16} /> {account.label}
              </button>
            ))}
          </div>

          <form ref={formRef} onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-subtle mb-2 uppercase tracking-wider">Email</label>
              <div className="relative">
                <span className="absolute left-4 top-1/2 -translate-y-1/2">
                  <Icon name="mail" size={18} className="text-muted" />
                </span>
                <input
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="input-glass pl-11"
                  type="email"
                  required
                  id="login-email"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-subtle mb-2 uppercase tracking-wider">Password</label>
              <div className="relative">
                <span className="absolute left-4 top-1/2 -translate-y-1/2">
                  <Icon name="lock" size={18} className="text-muted" />
                </span>
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="input-glass pl-11 pr-11"
                  required
                  id="login-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-muted hover:text-subtle transition-colors"
                >
                  <Icon name={showPassword ? "visibility_off" : "visibility"} size={18} />
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/20 animate-fade-in">
                <Icon name="error" size={16} className="text-red-400 flex-shrink-0" />
                <p className="text-sm text-red-400">{error}</p>
              </div>
            )}

            <button type="submit" disabled={loading} className="btn-primary w-full flex items-center justify-center gap-2 py-3" id="login-submit">
              {loading ? (
                <>
                  <div className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                  Signing in…
                </>
              ) : (
                <>
                  <Icon name="login" size={18} />
                  Sign in
                </>
              )}
            </button>
          </form>

          <div className="relative my-5">
            <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-white/[0.06]" /></div>
            <div className="relative flex justify-center"><span className="bg-[#111827] px-3 text-[10px] uppercase tracking-wider text-muted">Optional</span></div>
          </div>

          <button
            type="button"
            onClick={continueAsGuest}
            disabled={loading || guestLoading}
            className="btn-secondary w-full flex items-center justify-center gap-2 py-3"
            id="guest-access-button"
          >
            {guestLoading ? (
              <><div className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" /> Opening viewer…</>
            ) : (
              <><Icon name="visibility" size={18} /> Continue as guest</>
            )}
          </button>
          <p className="text-[10px] text-muted text-center mt-2">Read-only consumer view</p>
        </div>

        {/* Demo Accounts */}
        <div className="mt-6 animate-fade-in-up" style={{ animationDelay: "0.2s" }}>
          <p className="text-xs text-muted text-center mb-3 uppercase tracking-wider font-medium">Quick access — demo accounts</p>
          <div className="grid grid-cols-3 gap-3">
            {DEMO_ACCOUNTS.map((acct) => (
              <button
                key={acct.label}
                onClick={() => selectDemo(acct)}
                className="glass-card p-4 text-center hover:border-accent/30 hover:bg-accent/5 transition-all duration-300 group cursor-pointer"
              >
                <div className="w-10 h-10 rounded-xl bg-white/[0.04] flex items-center justify-center mx-auto mb-2 group-hover:bg-accent/10 group-hover:scale-110 transition-all duration-300">
                  <Icon name={acct.icon} size={20} className="text-subtle group-hover:text-accent-light transition-colors" />
                </div>
                <p className="text-xs font-semibold text-white">{acct.label}</p>
                <p className="text-[10px] text-muted mt-0.5">{acct.desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-[10px] text-muted mt-6">
          Built for Intain Campus FinTech Challenge 2026 · Hash-chain audited records
        </p>
      </div>
    </div>
  );
}
