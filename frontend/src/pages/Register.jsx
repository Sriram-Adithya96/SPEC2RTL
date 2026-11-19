import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Cpu, Loader2, Lock, Mail, User } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { errorMessage } from "../api";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    if (!email || !username || !password) {
      setError("Please fill in all fields.");
      return;
    }
    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setError("");
    setLoading(true);
    try {
      await register(email, username, password);
      navigate("/");
    } catch (err) {
      setError(errorMessage(err, "Failed to create account. Email may already be in use."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-[80vh] items-center justify-center px-4 py-12">
      <div className="glass w-full max-w-md p-6 sm:p-8 rounded-2xl border border-[var(--line)] shadow-2xl">
        {/* Brand Header */}
        <div className="text-center mb-8">
          <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-xl bg-[rgba(167,139,250,0.1)] text-[var(--acc2)]">
            <Cpu size={26} />
          </div>
          <p className="font-mono text-xs font-bold uppercase tracking-[0.16em] text-[var(--acc2)]">SPEC2RTL</p>
          <h1 className="mt-1 font-mono text-2xl font-extrabold text-[var(--text)]">Create Account</h1>
          <p className="mt-1.5 text-xs text-[var(--mute)]">Join SPEC2RTL to store your pipeline runs & RTL designs</p>
        </div>

        {error && (
          <div className="mb-5 rounded-lg border border-[rgba(248,113,113,0.3)] bg-[rgba(248,113,113,0.1)] p-3 text-xs font-mono text-[var(--bad)]">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block font-mono text-xs font-semibold text-[var(--mute)] mb-1.5">
              Username
            </label>
            <div className="relative">
              <User size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--mute)]" />
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="adithya_rtl"
                className="w-full rounded-lg border border-[var(--line)] bg-[rgba(10,14,20,0.6)] pl-10 pr-4 py-2.5 font-mono text-xs text-[var(--text)] outline-none transition placeholder:text-[var(--mute)] focus:border-[var(--acc)] focus:ring-1 focus:ring-[var(--acc)]"
              />
            </div>
          </div>

          <div>
            <label className="block font-mono text-xs font-semibold text-[var(--mute)] mb-1.5">
              Email Address
            </label>
            <div className="relative">
              <Mail size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--mute)]" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="developer@example.com"
                className="w-full rounded-lg border border-[var(--line)] bg-[rgba(10,14,20,0.6)] pl-10 pr-4 py-2.5 font-mono text-xs text-[var(--text)] outline-none transition placeholder:text-[var(--mute)] focus:border-[var(--acc)] focus:ring-1 focus:ring-[var(--acc)]"
              />
            </div>
          </div>

          <div>
            <label className="block font-mono text-xs font-semibold text-[var(--mute)] mb-1.5">
              Password (min. 6 characters)
            </label>
            <div className="relative">
              <Lock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--mute)]" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full rounded-lg border border-[var(--line)] bg-[rgba(10,14,20,0.6)] pl-10 pr-4 py-2.5 font-mono text-xs text-[var(--text)] outline-none transition placeholder:text-[var(--mute)] focus:border-[var(--acc)] focus:ring-1 focus:ring-[var(--acc)]"
              />
            </div>
          </div>

          <div>
            <label className="block font-mono text-xs font-semibold text-[var(--mute)] mb-1.5">
              Confirm Password
            </label>
            <div className="relative">
              <Lock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--mute)]" />
              <input
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full rounded-lg border border-[var(--line)] bg-[rgba(10,14,20,0.6)] pl-10 pr-4 py-2.5 font-mono text-xs text-[var(--text)] outline-none transition placeholder:text-[var(--mute)] focus:border-[var(--acc)] focus:ring-1 focus:ring-[var(--acc)]"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="mt-2 w-full min-h-[42px] inline-flex items-center justify-center gap-2 rounded-lg bg-[var(--acc2)] px-4 py-2.5 font-mono text-xs font-bold text-white transition hover:brightness-110 disabled:opacity-50"
          >
            {loading ? (
              <>
                <Loader2 size={14} className="animate-spin" /> Creating Account…
              </>
            ) : (
              "Create Account →"
            )}
          </button>
        </form>

        <div className="mt-6 flex items-center justify-between border-t border-[var(--line)] pt-4 text-xs font-mono">
          <span className="text-[var(--mute)]">Already registered?</span>
          <Link to="/login" className="font-semibold text-[var(--acc)] hover:underline">
            Sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
