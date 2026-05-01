import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { listAdminUsers, updateAdminUserRole, type ApiUser, type UserRole } from "../../lib/api";
import { useAuthOptional } from "../../contexts/AuthContext";
import { isAdmin } from "../../lib/api";
import { Loader2 } from "lucide-react";

export function AdminUsersTab() {
  const auth = useAuthOptional();
  const [users, setUsers] = useState<ApiUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savingRoleId, setSavingRoleId] = useState<string | null>(null);

  useEffect(() => {
    if (!auth?.user || !isAdmin(auth.user)) return;
    setLoading(true);
    listAdminUsers()
      .then(setUsers)
      .catch(() => {
        // Non-critical: silently ignore
      })
      .finally(() => setLoading(false));
  }, [auth?.user]);

  const handleRoleChange = async (userId: string, role: UserRole) => {
    setSavingRoleId(userId);
    setError(null);
    try {
      const updated = await updateAdminUserRole(userId, role);
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSavingRoleId(null);
    }
  };

  return (
    <Card className="mb-8 dark:bg-slate-900 dark:border-slate-800">
      <CardHeader>
        <CardTitle className="dark:text-slate-100">Benutzerverwaltung</CardTitle>
        <CardDescription className="dark:text-slate-400">
          Rollen der registrierten Nutzer anpassen (viewer, editor, admin).
        </CardDescription>
      </CardHeader>
      <CardContent>
        {error && <p className="text-red-600 dark:text-red-400 mb-3 text-sm">{error}</p>}
        {loading ? (
          <p className="text-slate-600 dark:text-slate-400">Lade Nutzer…</p>
        ) : users.length === 0 ? (
          <p className="text-slate-500 dark:text-slate-400 text-sm">Keine Nutzer gefunden.</p>
        ) : (
          <div className="space-y-2">
            {users.map((u) => (
              <div
                key={u.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-200 dark:border-slate-700 p-3"
              >
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-slate-900 dark:text-slate-100 truncate">
                    {u.display_name || "—"}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400 truncate">
                    {u.email ?? "Keine E-Mail"} · ID: {u.id.slice(0, 8)}…
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {savingRoleId === u.id ? (
                    <Loader2 className="size-4 animate-spin text-slate-500" />
                  ) : (
                    <Select
                      value={u.role ?? "viewer"}
                      onValueChange={(value) => handleRoleChange(u.id, value as UserRole)}
                    >
                      <SelectTrigger className="w-32">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="viewer">Viewer</SelectItem>
                        <SelectItem value="editor">Editor</SelectItem>
                        <SelectItem value="admin">Admin</SelectItem>
                      </SelectContent>
                    </Select>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
