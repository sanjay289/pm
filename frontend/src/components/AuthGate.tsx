"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getSession, logout } from "@/lib/auth";
import { KanbanBoard } from "@/components/KanbanBoard";

export const AuthGate = () => {
  const router = useRouter();
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    let active = true;

    getSession().then((isAuthenticated) => {
      if (!active) {
        return;
      }
      if (isAuthenticated) {
        setAuthenticated(true);
      } else {
        router.replace("/login");
      }
    });

    return () => {
      active = false;
    };
  }, [router]);

  const handleLogout = async () => {
    await logout();
    router.replace("/login");
  };

  if (!authenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-[var(--gray-text)]">
        Loading…
      </div>
    );
  }

  return <KanbanBoard onLogout={handleLogout} onUnauthorized={() => router.replace("/login")} />;
};
