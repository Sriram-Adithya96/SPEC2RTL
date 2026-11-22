import { createContext, useContext, useEffect, useState } from "react";
import { api, errorMessage } from "../api";

const AuthContext = createContext(null);
const TOKEN_KEY = "spec2rtl_auth_token";
const USER_KEY = "spec2rtl_auth_user";

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => {
    try {
      return localStorage.getItem(TOKEN_KEY) || null;
    } catch {
      return null;
    }
  });

  const [user, setUser] = useState(() => {
    try {
      const raw = localStorage.getItem(USER_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });

  const [loading, setLoading] = useState(true);

  // Validate token on initial mount
  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    api
      .get("/auth/me")
      .then((res) => {
        setUser(res.data);
        localStorage.setItem(USER_KEY, JSON.stringify(res.data));
      })
      .catch(() => {
        // Token expired or invalid
        logout();
      })
      .finally(() => {
        setLoading(false);
      });
  }, [token]);

  async function login(email, password) {
    const res = await api.post("/auth/login", { email, password });
    const { token: nextToken, user: nextUser } = res.data;
    setToken(nextToken);
    setUser(nextUser);
    localStorage.setItem(TOKEN_KEY, nextToken);
    localStorage.setItem(USER_KEY, JSON.stringify(nextUser));
    return nextUser;
  }

  async function register(email, username, password) {
    const res = await api.post("/auth/register", { email, username, password });
    const { token: nextToken, user: nextUser } = res.data;
    setToken(nextToken);
    setUser(nextUser);
    localStorage.setItem(TOKEN_KEY, nextToken);
    localStorage.setItem(USER_KEY, JSON.stringify(nextUser));
    return nextUser;
  }

  async function resetPassword(email, newPassword) {
    const res = await api.post("/auth/reset-password", {
      email,
      new_password: newPassword,
    });
    return res.data;
  }

  function logout() {
    setToken(null);
    setUser(null);
    try {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      localStorage.removeItem("spec2rtl-my-runs");
      sessionStorage.removeItem("spec2rtl-active-run");
    } catch {}
  }

  const value = {
    user,
    token,
    loading,
    isAuthenticated: Boolean(token && user),
    login,
    register,
    resetPassword,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
