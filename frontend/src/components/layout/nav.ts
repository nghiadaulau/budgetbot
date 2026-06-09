import {
  LayoutDashboard,
  ReceiptText,
  PieChart,
  Settings,
  type LucideIcon,
} from "lucide-react";
import type { StringKey } from "@/i18n/strings";

export interface NavItem {
  to: string;
  labelKey: StringKey;
  icon: LucideIcon;
}

export const NAV_ITEMS: NavItem[] = [
  { to: "/", labelKey: "nav.dashboard", icon: LayoutDashboard },
  { to: "/transactions", labelKey: "nav.transactions", icon: ReceiptText },
  { to: "/insights", labelKey: "nav.insights", icon: PieChart },
  { to: "/settings", labelKey: "nav.settings", icon: Settings },
];
