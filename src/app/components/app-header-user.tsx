import { useAuthOptional } from "../contexts/AuthContext";
import { Button } from "./ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import { LogOut, User } from "lucide-react";

/**
 * Shows current user and logout in the header when auth is available.
 * When OIDC is enabled, user is set after login. When disabled, user may come from /me.
 */
export function AppHeaderUser() {
  const auth = useAuthOptional();
  if (!auth?.user) return null;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="gap-2">
          <User className="size-4" />
          <span className="max-w-[140px] truncate">{auth.user.display_name || auth.user.email || "Profil"}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => auth.logout()} className="gap-2 cursor-pointer">
          <LogOut className="size-4" />
          Abmelden
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
