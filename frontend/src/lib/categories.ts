import {
  Utensils,
  Car,
  ShoppingBag,
  ReceiptText,
  Clapperboard,
  HeartPulse,
  GraduationCap,
  Wallet,
  ArrowLeftRight,
  CircleDashed,
  type LucideIcon,
} from "lucide-react";

/**
 * The 10 canonical categories — must match the backend enum exactly
 * (src/categories.py CATEGORIES). Salary is treated as income everywhere.
 */
export const CATEGORIES = [
  "Food",
  "Transport",
  "Shopping",
  "Bills",
  "Entertainment",
  "Health",
  "Education",
  "Salary",
  "Transfer",
  "Other",
] as const;

export type Category = (typeof CATEGORIES)[number];

export interface CategoryMeta {
  /** Vietnamese label (primary UI language). */
  vi: string;
  /** English label. */
  en: string;
  icon: LucideIcon;
  /** Badge / chart color — chosen to read on both light and dark surfaces. */
  color: string;
}

export const CATEGORY_META: Record<Category, CategoryMeta> = {
  Food: { vi: "Ăn uống", en: "Food", icon: Utensils, color: "#ea580c" },
  Transport: { vi: "Di chuyển", en: "Transport", icon: Car, color: "#0891b2" },
  Shopping: { vi: "Mua sắm", en: "Shopping", icon: ShoppingBag, color: "#db2777" },
  Bills: { vi: "Hóa đơn", en: "Bills", icon: ReceiptText, color: "#d97706" },
  Entertainment: {
    vi: "Giải trí",
    en: "Entertainment",
    icon: Clapperboard,
    color: "#7c3aed",
  },
  Health: { vi: "Sức khỏe", en: "Health", icon: HeartPulse, color: "#0d9488" },
  Education: {
    vi: "Giáo dục",
    en: "Education",
    icon: GraduationCap,
    color: "#4f46e5",
  },
  Salary: { vi: "Thu nhập", en: "Salary", icon: Wallet, color: "#059669" },
  Transfer: {
    vi: "Chuyển khoản",
    en: "Transfer",
    icon: ArrowLeftRight,
    color: "#475569",
  },
  Other: { vi: "Khác", en: "Other", icon: CircleDashed, color: "#64748b" },
};

export function categoryLabel(cat: string, lang: "vi" | "en"): string {
  const meta = CATEGORY_META[cat as Category];
  return meta ? meta[lang] : cat;
}

export function categoryColor(cat: string): string {
  return CATEGORY_META[cat as Category]?.color ?? "#64748b";
}

/**
 * Lightweight keyword categorizer for the Quick Add auto-suggest.
 * Mirrors the backend LocalAI keyword rules so suggestions feel consistent.
 * The real AI categorization still happens server-side on upload.
 */
const KEYWORDS: Record<Category, string[]> = {
  Salary: ["salary", "lương", "luong", "thu nhập", "thu nhap", "payroll", "freelance", "payout"],
  Transfer: ["transfer", "chuyển khoản", "chuyen khoan", "vnpay", "atm", "ck "],
  Bills: [
    "evn", "điện", "dien", "nước", "nuoc", "internet", "viettel", "vnpt",
    "fpt", "gas", "petrolimex", "hóa đơn", "hoa don", "bill", "tiền nhà", "rent",
  ],
  Health: [
    "pharmacy", "pharmacity", "guardian", "long châu", "long chau", "hospital",
    "bệnh viện", "benh vien", "clinic", "thuốc", "medlatec",
  ],
  Education: [
    "giáo dục", "giao duc", "học phí", "hoc phi", "udemy", "coursera",
    "khóa học", "khoa hoc", "tuition", "trường", "school",
  ],
  Entertainment: [
    "cgv", "galaxy cinema", "lotte cinema", "cinema", "rạp", "game",
    "netflix", "spotify", "youtube", "concert", "steam",
  ],
  Food: [
    "coffee", "cafe", "cà phê", "ca phe", "highlands", "phúc long", "phở", "pho",
    "food", "ăn", "nhà hàng", "restaurant", "lunch", "dinner", "grab food",
    "shopee food", "trà sữa", "kfc", "pizza", "winmart", "vinmart", "bigc",
    "co.opmart", "lotte mart", "bún", "cơm",
  ],
  Transport: [
    "grab", "be ", "xanh sm", "taxi", "metro", "bus", "xăng", "fuel",
    "vinfast", "gửi xe", "parking",
  ],
  Shopping: [
    "shopee", "lazada", "tiki", "amazon", "vincom", "mall", "shop", "mua",
    "store", "uniqlo",
  ],
  Other: [],
};

export function suggestCategory(
  description: string,
  amount?: number,
): Category {
  const d = description.toLowerCase();
  for (const cat of CATEGORIES) {
    if (KEYWORDS[cat].some((kw) => d.includes(kw))) return cat;
  }
  if (typeof amount === "number" && amount > 0) return "Salary";
  return "Other";
}
