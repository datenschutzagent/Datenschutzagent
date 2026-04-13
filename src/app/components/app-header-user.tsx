import { Link } from "react-router";
import { useAuthOptional } from "../contexts/AuthContext";
import { isAdmin } from "../lib/api";
import { Button } from "./ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import { LogOut, Settings, User, UserRound } from "lucide-react";

/**
 * Shows current user and logout in the header when auth is available.
 * When OIDC is enabled, user is set after login. When disabled, user may come from /me.
 */
export function AppHeaderUser() {
  const auth = useAuthOptional();
  if (!auth?.user) return null;

  const displayName = auth.user.display_name || auth.user.email || "Profil";
  const admin = isAdmin(auth.user);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="gap-2">
          <User className="size-4" />
          <span className="max-w-[140px] truncate">{displayName}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[180px]">
        <DropdownMenuLabel className="font-normal">
          <p className="font-medium truncate">{auth.user.display_name || "Profil"}</p>
          {auth.user.email && (
            <p className="text-xs text-muted-foreground truncate">{auth.user.email}</p>
          )}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild className="gap-2 cursor-pointer">
          <Link to="/profile">
            <UserRound className="size-4" />
            Mein Profil
          </Link>
        </DropdownMenuItem>
        {admin && (
          <DropdownMenuItem asChild className="gap-2 cursor-pointer">
            <Link to="/admin">
              <Settings className="size-4" />
              Verwaltung
            </Link>
          </DropdownMenuItem>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => auth.logout()} className="gap-2 cursor-pointer">
          <LogOut className="size-4" />
          Abmelden
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
