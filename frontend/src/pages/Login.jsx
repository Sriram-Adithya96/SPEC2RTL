import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { errorMessage } from "../api";
import RtlChipHero from "../components/RtlChipHero";

export default function Login() {
  const { login, register } = useAuth();
  const [isRegisterMode, setIsRegisterMode] = useState(false);

  // Form states
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});

  useEffect(() => {
    document.title = isRegisterMode
      ? "Create account · Spec2RTL"
      : "Sign in · Spec2RTL";
  }, [isRegisterMode]);

  function validate() {
    const errs = {};
    const trimmedEmail = email.trim();

    if (!trimmedEmail) {
      errs.email = "Please enter your email address.";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      errs.email = "Please enter a valid email address.";
    }

    if (!password) {
      errs.password = "Please enter your password.";
    } else if (isRegisterMode && password.length < 6) {
      errs.password = "Password must be at least 6 characters.";
    }

    if (isRegisterMode) {
      if (!username.trim()) {
        errs.username = "Please choose a username.";
      }
      if (password !== confirmPassword) {
        errs.confirmPassword = "Passwords do not match.";
      }
    }

    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (loading) return; // Prevent double submits

    setError("");
    if (!validate()) return;

    setLoading(true);
    try {
      if (isRegisterMode) {
        await register(email.trim().toLowerCase(), username.trim(), password);
      } else {
        await login(email.trim().toLowerCase(), password);
      }
    } catch (err) {
      const serverMsg = errorMessage(err, "");
      if (isRegisterMode) {
        setError(serverMsg || "Could not create account. Please try again.");
      } else {
        // Standard form-level alert for sign-in failure
        setError(serverMsg || "Email or password is incorrect.");
      }
    } finally {
      setLoading(false);
    }
  }

  function handleForgotPassword() {
    if (loading) return;
    setError("Password reset instructions will be sent to your email. (Feature coming soon)");
  }

  return (
    <div
      className="min-h-screen w-full flex items-center justify-center px-4 py-8 sm:px-6 lg:px-10 relative overflow-hidden font-mono"
      style={{
        backgroundColor: "#050713",
        backgroundImage:
          "radial-gradient(ellipse at 50% 50%, rgba(22, 28, 64, 0.5) 0%, rgba(6, 8, 20, 0.95) 70%, #03040a 100%)",
      }}
    >
      {/* Soft Vignette and Faint Circuit Grid Pattern */}
      <div
        className="absolute inset-0 pointer-events-none opacity-20"
        style={{
          backgroundImage:
            "linear-gradient(to right, rgba(99, 102, 241, 0.12) 1px, transparent 1px), linear-gradient(to bottom, rgba(99, 102, 241, 0.12) 1px, transparent 1px)",
          backgroundSize: "36px 36px",
        }}
      />

      {/* Main container: Left Hero Illustration + Right Login Card (Vertically & Horizontally Balanced) */}
      <div className="relative z-10 w-full max-w-[1240px] mx-auto flex items-center justify-center lg:gap-10 xl:gap-14 py-6 px-4 sm:px-6 lg:px-8">
        {/* ── Left Side: RTL Chip Hero with Centered Caption (hidden below 1024px) ── */}
        <div className="hidden lg:flex flex-col items-center justify-center flex-1 w-full max-w-[640px] xl:max-w-[680px]">
          <RtlChipHero className="w-full h-auto select-none pointer-events-none drop-shadow-[0_25px_60px_rgba(79,70,229,0.35)]" />
          <p className="mt-4 text-center font-mono text-[13px] text-[#c7d2fe] tracking-wider select-none opacity-90">
            Spec in. Verified Verilog out.
          </p>
        </div>

        {/* ── Right Side: Production-Ready Login Box ───────────────── */}
        <div className="w-full max-w-[410px] shrink-0">
          <div
            className="w-full rounded-[28px] p-7 sm:p-9 shadow-2xl relative transition-all duration-300"
            style={{
              backgroundColor: "rgba(13, 17, 36, 0.92)",
              border: "1px solid rgba(42, 47, 92, 0.9)",
              backdropFilter: "blur(20px)",
              boxShadow: "0 25px 60px -15px rgba(3, 5, 15, 0.95), 0 0 35px rgba(99, 102, 241, 0.14)",
            }}
          >
            {/* Top Logo Badge: [ S ] SPEC2RTL */}
            <div className="flex items-center gap-2.5 mb-6">
              <span
                className="grid h-7 w-7 place-items-center rounded-lg text-xs font-black shadow-md select-none"
                style={{
                  background: "linear-gradient(135deg, #93c5fd, #60a5fa)",
                  color: "#080c1e",
                }}
              >
                S
              </span>
              <span className="text-sm font-extrabold tracking-wider text-white">
                SPEC2RTL
              </span>
            </div>

            {/* Title & Subtitle in sentence case */}
            <h1 className="text-2xl font-bold tracking-tight text-white mb-2">
              {isRegisterMode ? "Create an account" : "Welcome back"}
            </h1>
            <p className="text-xs text-[#94a3b8] leading-relaxed mb-6">
              {isRegisterMode
                ? "Join Spec2RTL to store your pipeline runs & RTL designs."
                : "Sign in to turn your hardware spec into verified Verilog."}
            </p>

            {/* Form-level Error Alert Banner */}
            {error && (
              <div
                role="alert"
                className="mb-5 rounded-xl border border-[rgba(248,113,113,0.35)] bg-[rgba(248,113,113,0.12)] p-3 text-xs text-[#f87171] leading-relaxed flex items-start gap-2 select-none"
              >
                <span>{error}</span>
              </div>
            )}

            {/* Form with accessibility labels and loading states */}
            <form onSubmit={handleSubmit} noValidate className="space-y-4">
              {/* Username (Only in Register Mode) */}
              {isRegisterMode && (
                <div>
                  <label htmlFor="login-username" className="sr-only">
                    Username
                  </label>
                  <input
                    id="login-username"
                    name="username"
                    type="text"
                    autoComplete="username"
                    disabled={loading}
                    value={username}
                    onChange={(e) => {
                      setUsername(e.target.value);
                      if (fieldErrors.username) {
                        setFieldErrors((prev) => ({ ...prev, username: "" }));
                      }
                    }}
                    placeholder="Username"
                    className={`w-full rounded-xl px-4 py-3 text-xs text-white outline-none transition-all placeholder:text-[#cbd5e1] bg-[#0e1328] border ${
                      fieldErrors.username
                        ? "border-[#f87171] focus:ring-[#f87171]/40"
                        : "border-[#2a2f5c] focus:border-[#818cf8] focus:ring-[#818cf8]/50"
                    } focus:outline-none focus:ring-2 disabled:opacity-50`}
                  />
                  {fieldErrors.username && (
                    <p className="mt-1 text-[11px] text-[#f87171] select-none">
                      {fieldErrors.username}
                    </p>
                  )}
                </div>
              )}

              {/* Email */}
              <div>
                <label htmlFor="login-email" className="sr-only">
                  Email address
                </label>
                <input
                  id="login-email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  disabled={loading}
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (fieldErrors.email) {
                      setFieldErrors((prev) => ({ ...prev, email: "" }));
                    }
                  }}
                  placeholder="Email"
                  className={`w-full rounded-xl px-4 py-3 text-xs text-white outline-none transition-all placeholder:text-[#cbd5e1] bg-[#0e1328] border ${
                    fieldErrors.email
                      ? "border-[#f87171] focus:ring-[#f87171]/40"
                      : "border-[#2a2f5c] focus:border-[#818cf8] focus:ring-[#818cf8]/50"
                  } focus:outline-none focus:ring-2 disabled:opacity-50`}
                />
                {fieldErrors.email && (
                  <p className="mt-1 text-[11px] text-[#f87171] select-none">
                    {fieldErrors.email}
                  </p>
                )}
              </div>

              {/* Password */}
              <div className="space-y-1.5">
                <div className="relative">
                  <label htmlFor="login-password" className="sr-only">
                    Password
                  </label>
                  <input
                    id="login-password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete={isRegisterMode ? "new-password" : "current-password"}
                    disabled={loading}
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      if (fieldErrors.password) {
                        setFieldErrors((prev) => ({ ...prev, password: "" }));
                      }
                    }}
                    placeholder="Password"
                    className={`w-full rounded-xl pl-4 pr-16 py-3 text-xs text-white outline-none transition-all placeholder:text-[#cbd5e1] bg-[#0e1328] border ${
                      fieldErrors.password
                        ? "border-[#f87171] focus:ring-[#f87171]/40"
                        : "border-[#2a2f5c] focus:border-[#818cf8] focus:ring-[#818cf8]/50"
                    } focus:outline-none focus:ring-2 disabled:opacity-50`}
                  />
                  <button
                    type="button"
                    disabled={loading}
                    aria-pressed={showPassword}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-xs font-semibold text-[#8b9bb4] hover:text-white focus:outline-none focus:text-[#818cf8] transition select-none disabled:opacity-40 cursor-pointer"
                  >
                    {showPassword ? "Hide" : "Show"}
                  </button>
                </div>
                {fieldErrors.password && (
                  <p className="mt-1 text-[11px] text-[#f87171] select-none">
                    {fieldErrors.password}
                  </p>
                )}

                {/* Forgot Password Link (right-aligned under password field) */}
                {!isRegisterMode && (
                  <div className="flex justify-end pt-0.5">
                    <button
                      type="button"
                      disabled={loading}
                      onClick={handleForgotPassword}
                      className="text-[11px] text-[#818cf8] hover:text-[#a5b4fc] focus:outline-none focus:underline transition underline underline-offset-2 cursor-pointer select-none disabled:opacity-50"
                    >
                      Forgot password?
                    </button>
                  </div>
                )}
              </div>

              {/* Confirm Password (Only in Register Mode) */}
              {isRegisterMode && (
                <div>
                  <label htmlFor="login-confirm-password" className="sr-only">
                    Confirm password
                  </label>
                  <input
                    id="login-confirm-password"
                    name="confirmPassword"
                    type={showPassword ? "text" : "password"}
                    autoComplete="new-password"
                    disabled={loading}
                    value={confirmPassword}
                    onChange={(e) => {
                      setConfirmPassword(e.target.value);
                      if (fieldErrors.confirmPassword) {
                        setFieldErrors((prev) => ({ ...prev, confirmPassword: "" }));
                      }
                    }}
                    placeholder="Confirm password"
                    className={`w-full rounded-xl px-4 py-3 text-xs text-white outline-none transition-all placeholder:text-[#cbd5e1] bg-[#0e1328] border ${
                      fieldErrors.confirmPassword
                        ? "border-[#f87171] focus:ring-[#f87171]/40"
                        : "border-[#2a2f5c] focus:border-[#818cf8] focus:ring-[#818cf8]/50"
                    } focus:outline-none focus:ring-2 disabled:opacity-50`}
                  />
                  {fieldErrors.confirmPassword && (
                    <p className="mt-1 text-[11px] text-[#f87171] select-none">
                      {fieldErrors.confirmPassword}
                    </p>
                  )}
                </div>
              )}

              {/* Primary Action Button: Sign in / Create account */}
              <button
                type="submit"
                disabled={loading}
                className="w-full min-h-[44px] inline-flex items-center justify-center gap-2 rounded-xl text-xs font-bold text-white transition-all duration-150 hover:brightness-110 hover:shadow-[0_8px_25px_rgba(108,126,248,0.5)] active:scale-[0.98] active:brightness-95 focus:outline-none focus:ring-2 focus:ring-[#818cf8] focus:ring-offset-2 focus:ring-offset-[#0d1124] disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none mt-1 cursor-pointer"
                style={{
                  background: "linear-gradient(135deg, #7c8cf8, #5b6df6)",
                  boxShadow: "0 6px 22px -3px rgba(108, 126, 248, 0.55)",
                }}
              >
                {loading ? (
                  <>
                    <Loader2 size={15} className="animate-spin" />
                    {isRegisterMode ? "Creating account…" : "Signing in…"}
                  </>
                ) : isRegisterMode ? (
                  "Create account"
                ) : (
                  "Sign in"
                )}
              </button>
            </form>

            {/* Footer toggle link with high contrast (>= 4.5:1) */}
            <div className="mt-6 text-center text-xs text-[#cbd5e1]">
              {isRegisterMode ? (
                <>
                  Already registered?{" "}
                  <button
                    type="button"
                    disabled={loading}
                    onClick={() => {
                      setIsRegisterMode(false);
                      setError("");
                      setFieldErrors({});
                    }}
                    className="font-semibold text-[#818cf8] hover:text-[#a5b4fc] focus:outline-none focus:underline transition cursor-pointer underline underline-offset-2 disabled:opacity-50"
                  >
                    Sign in
                  </button>
                </>
              ) : (
                <>
                  New to Spec2RTL?{" "}
                  <button
                    type="button"
                    disabled={loading}
                    onClick={() => {
                      setIsRegisterMode(true);
                      setError("");
                      setFieldErrors({});
                    }}
                    className="font-semibold text-[#818cf8] hover:text-[#a5b4fc] focus:outline-none focus:underline transition cursor-pointer underline underline-offset-2 disabled:opacity-50"
                  >
                    Create account
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
