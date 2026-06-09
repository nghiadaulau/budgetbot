import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { useUi } from "@/context/ui";
import { currentMonth, lastNMonths, formatMonthLabel } from "@/lib/format";
import { CalendarDays } from "lucide-react";

export function MonthPicker() {
  const { month, setMonth } = useUi();
  const months = lastNMonths(currentMonth(), 12).reverse();
  return (
    <Select value={month} onValueChange={setMonth}>
      <SelectTrigger className="h-9 w-[150px] gap-2" aria-label="Chọn tháng">
        <CalendarDays className="size-4 opacity-60" />
        <SelectValue>{formatMonthLabel(month)}</SelectValue>
      </SelectTrigger>
      <SelectContent>
        {months.map((m) => (
          <SelectItem key={m} value={m}>
            {formatMonthLabel(m)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
