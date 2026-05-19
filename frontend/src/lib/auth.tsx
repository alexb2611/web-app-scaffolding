"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";

import type { components } from "./api-types";
import { bootstrapSession, client, setAccessToken, unwrap } from "./api";

// ── Types ──────────────────────────────────────────────────────────────

export type User = components["schemas"]["UserResponse"];

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
}

interface AuthActions {
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => Promise<void>;
}

type AuthContextValue = AuthState & AuthActions;

// ── Context ────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}

// ── Provider ───────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // On mount, exchange the HttpOnly refresh cookie for a fresh in-memory
  // access token, then fetch the user profile.
  const bootstrap = useCallback(async () => {
    const ok = await bootstrapSession();
    if (!ok) {
      setUser(null);
      setIsLoading(false);
      return;
    }
    try {
      const u = await unwrap(client.GET("/api/v1/auth/me"));
      setUser(u);
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await unwrap(
      client.POST("/api/v1/auth/login", {
        body: { email, password },
      }),
    );
    setAccessToken(tokens.access_token);
    const u = await unwrap(client.GET("/api/v1/auth/me"));
    setUser(u);
  }, []);

  const register = useCallback(
    async (email: string, password: string, fullName?: string) => {
      await unwrap(
        client.POST("/api/v1/auth/register", {
          body: { email, password, full_name: fullName || null },
        }),
      );
      await login(email, password);
    },
    [login],
  );

  const logout = useCallback(async () => {
    try {
      await client.POST("/api/v1/auth/logout");
    } catch {
      // Even if the call fails, clear local state.
    }
    setAccessToken(null);
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      isAuthenticated: !!user,
      login,
      register,
      logout,
    }),
    [user, isLoading, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
