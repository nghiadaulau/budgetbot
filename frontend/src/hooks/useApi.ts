import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/api/client";
import type { Transaction, TransactionInput } from "@/api/types";
import type { Category } from "@/lib/categories";

export const keys = {
  transactions: (month?: string) => ["transactions", month ?? "all"] as const,
  summary: (month?: string) => ["summary", month ?? "all"] as const,
  budgets: (month?: string) => ["budgets", month ?? "all"] as const,
};

export function useTransactions(month?: string) {
  return useQuery({
    queryKey: keys.transactions(month),
    queryFn: () => api.listTransactions(month),
  });
}

/**
 * Full history (all pages) for cross-month aggregation on the dashboard.
 * Keyed under ["transactions", …] so invalidateAll() refreshes it too.
 */
export function useAllTransactions(month?: string) {
  return useQuery({
    queryKey: [...keys.transactions(month), "full"],
    queryFn: () => api.listAllTransactions(month),
  });
}

export function useSummary(month?: string) {
  return useQuery({
    queryKey: keys.summary(month),
    queryFn: () => api.getSummary(month),
  });
}

export function useBudgets(month?: string) {
  return useQuery({
    queryKey: keys.budgets(month),
    queryFn: () => api.getBudgets(month),
  });
}

/** Set/update a monthly budget cap, then refresh budget + summary views. */
export function useSetBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ category, amount }: { category: string; amount: number }) =>
      api.setBudget(category, amount),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["budgets"] });
      qc.invalidateQueries({ queryKey: ["summary"] });
    },
  });
}

/** Invalidate everything that depends on transaction data. */
export function invalidateAll(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ["transactions"] });
  qc.invalidateQueries({ queryKey: ["summary"] });
  qc.invalidateQueries({ queryKey: ["budgets"] });
}

/** Refresh all data views after an out-of-band write (e.g. CSV/receipt upload). */
export function useInvalidateData() {
  const qc = useQueryClient();
  return () => invalidateAll(qc);
}

export function useCreateTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: TransactionInput) => api.createTransaction(input),
    onSuccess: () => invalidateAll(qc),
  });
}

export function useDeleteTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteTransaction(id),
    onSuccess: () => invalidateAll(qc),
  });
}

export function useClearAll() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.clearAll(),
    onSuccess: () => invalidateAll(qc),
  });
}

/**
 * Optimistic category edit: patch every cached transactions list immediately,
 * roll back on error, then resync summary/budgets on settle.
 */
export function useUpdateCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, category }: { id: string; category: Category }) =>
      api.updateCategory(id, category),
    onMutate: async ({ id, category }) => {
      await qc.cancelQueries({ queryKey: ["transactions"] });
      const snapshots = qc.getQueriesData<Transaction[]>({
        queryKey: ["transactions"],
      });
      for (const [key, data] of snapshots) {
        if (!data) continue;
        qc.setQueryData<Transaction[]>(
          key,
          data.map((t) => (t.id === id ? { ...t, category } : t)),
        );
      }
      return { snapshots };
    },
    onError: (_err, _vars, ctx) => {
      ctx?.snapshots.forEach(([key, data]) => qc.setQueryData(key, data));
    },
    onSettled: () => invalidateAll(qc),
  });
}
