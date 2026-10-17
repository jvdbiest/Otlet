// SPDX-License-Identifier: AGPL-3.0-or-later
// The AI settings of the signed-in user (F05): what the instance offers, their providers, their
// profile, their budget, the « Tester » checks, the journal, and the instance policy.
import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, apiError, type components } from "./api/client.ts";

export type CatalogueView = components["schemas"]["CatalogueView"];
export type ModelView = components["schemas"]["ModelView"];
export type ProviderView = components["schemas"]["ProviderView"];
export type ProfileView = components["schemas"]["ProfileView"];
export type BudgetView = components["schemas"]["BudgetView"];
export type PolicyView = components["schemas"]["PolicyView"];
export type ProfileCheckView = components["schemas"]["ProfileCheckView"];
export type CallView = components["schemas"]["CallView"];

const KEY = ["ai"] as const;

export const catalogueQuery = queryOptions({
  queryKey: [...KEY, "catalogue"],
  queryFn: async (): Promise<CatalogueView> => {
    const { data, error, response } = await api.GET("/api/ai/catalogue");
    if (data === undefined) {
      throw apiError(response, error);
    }
    return data;
  },
});

export const providersQuery = queryOptions({
  queryKey: [...KEY, "providers"],
  queryFn: async (): Promise<ProviderView[]> => {
    const { data, error, response } = await api.GET("/api/ai/providers");
    if (data === undefined) {
      throw apiError(response, error);
    }
    return data;
  },
});

export const profileQuery = queryOptions({
  queryKey: [...KEY, "profile"],
  queryFn: async (): Promise<ProfileView> => {
    const { data, error, response } = await api.GET("/api/ai/profile");
    if (data === undefined) {
      throw apiError(response, error);
    }
    return data;
  },
});

export const budgetQuery = queryOptions({
  queryKey: [...KEY, "budget"],
  queryFn: async (): Promise<BudgetView> => {
    const { data, error, response } = await api.GET("/api/ai/budget");
    if (data === undefined) {
      throw apiError(response, error);
    }
    return data;
  },
});

export const policyQuery = queryOptions({
  queryKey: [...KEY, "policy"],
  queryFn: async (): Promise<PolicyView> => {
    const { data, error, response } = await api.GET("/api/ai/policy");
    if (data === undefined) {
      throw apiError(response, error);
    }
    return data;
  },
});

export const callsQuery = queryOptions({
  queryKey: [...KEY, "calls"],
  queryFn: async (): Promise<CallView[]> => {
    const { data, error, response } = await api.GET("/api/ai/calls");
    if (data === undefined) {
      throw apiError(response, error);
    }
    return data;
  },
});

export const checkQuery = (checkId: string) =>
  queryOptions({
    queryKey: [...KEY, "checks", checkId],
    queryFn: async (): Promise<ProfileCheckView> => {
      const { data, error, response } = await api.GET("/api/ai/checks/{check_id}", {
        params: { path: { check_id: checkId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    // The worker answers in seconds or minutes (a local model on the NAS): followed closely.
    refetchInterval: (query) => (query.state.data?.finished_at ? false : 2_000),
  });

function useRefresh() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: KEY });
}

export function useAddProvider() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (body: components["schemas"]["NewProvider"]) => {
      const { data, error, response } = await api.POST("/api/ai/providers", { body });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: refresh,
  });
}

export function useUpdateProvider() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: components["schemas"]["ProviderChanges"] }) => {
      const { data, error, response } = await api.PUT("/api/ai/providers/{provider_id}", {
        params: { path: { provider_id: id } },
        body,
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: refresh,
  });
}

export function useDeleteProvider() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (id: string) => {
      const { error, response } = await api.DELETE("/api/ai/providers/{provider_id}", {
        params: { path: { provider_id: id } },
      });
      if (!response.ok) {
        throw apiError(response, error);
      }
    },
    onSuccess: refresh,
  });
}

export function useSaveProfile() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (body: ProfileView) => {
      const { data, error, response } = await api.PUT("/api/ai/profile", { body });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: refresh,
  });
}

export function useSaveBudget() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (monthlyLimit: string) => {
      const { data, error, response } = await api.PUT("/api/ai/budget", {
        body: { monthly_limit: monthlyLimit },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: refresh,
  });
}

export function useSavePolicy() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (body: PolicyView) => {
      const { data, error, response } = await api.PUT("/api/ai/policy", { body });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: refresh,
  });
}

export function useStartCheck() {
  return useMutation({
    mutationFn: async () => {
      const { data, error, response } = await api.POST("/api/ai/checks");
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
  });
}

export type InstalledView = components["schemas"]["InstalledView"];
export type PullView = components["schemas"]["PullView"];

/** The models installed on the local engine (Ollama) of a provider, read from the engine. */
export const installedQuery = (providerId: string) =>
  queryOptions({
    queryKey: [...KEY, "providers", providerId, "models"],
    queryFn: async (): Promise<InstalledView> => {
      const { data, error, response } = await api.GET("/api/ai/providers/{provider_id}/models", {
        params: { path: { provider_id: providerId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    retry: false,
    staleTime: 30_000,
  });

export const pullQuery = (pullId: string) =>
  queryOptions({
    queryKey: [...KEY, "pulls", pullId],
    queryFn: async (): Promise<PullView> => {
      const { data, error, response } = await api.GET("/api/ai/pulls/{pull_id}", {
        params: { path: { pull_id: pullId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    // A download takes minutes: followed every two seconds until it ends.
    refetchInterval: (query) => (query.state.data?.finished_at ? false : 2_000),
  });

export function useStartPull() {
  return useMutation({
    mutationFn: async ({ providerId, model }: { providerId: string; model: string }) => {
      const { data, error, response } = await api.POST("/api/ai/providers/{provider_id}/pulls", {
        params: { path: { provider_id: providerId } },
        body: { model },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
  });
}
