// SPDX-License-Identifier: AGPL-3.0-or-later
// The signed-in user and their workspaces, cached by TanStack Query.
import { queryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, apiError, setCsrfToken, type SessionView, type WorkspaceView } from "./api/client.ts";

/** The current session, or null when nobody is signed in. */
export const sessionQuery = queryOptions({
  queryKey: ["session"],
  queryFn: async (): Promise<SessionView | null> => {
    const { data, error, response } = await api.GET("/api/auth/session");
    if (response.status === 401) {
      setCsrfToken(null);
      return null;
    }
    if (data === undefined) {
      throw apiError(response, error);
    }
    setCsrfToken(data.csrf_token);
    return data;
  },
  staleTime: 60_000,
  retry: false,
});

export const workspacesQuery = queryOptions({
  queryKey: ["workspaces"],
  queryFn: async (): Promise<WorkspaceView[]> => {
    const { data, error, response } = await api.GET("/api/workspaces");
    if (data === undefined) {
      throw apiError(response, error);
    }
    return data;
  },
});

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (credentials: { login: string; password: string }) => {
      const { data, error, response } = await api.POST("/api/auth/login", { body: credentials });
      if (data === undefined) {
        throw apiError(response, error);
      }
      setCsrfToken(data.csrf_token);
      return data;
    },
    onSuccess: (session) => {
      queryClient.setQueryData(sessionQuery.queryKey, session);
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { error, response } = await api.POST("/api/auth/logout");
      // 401: already signed out, which is the goal.
      if (!response.ok && response.status !== 401) {
        throw apiError(response, error);
      }
    },
    onSuccess: () => {
      setCsrfToken(null);
      queryClient.clear();
      queryClient.setQueryData(sessionQuery.queryKey, null);
    },
  });
}

/** The workspace of the user (É1 has a single one per user, ROADMAP §5.2), once known. */
export function useWorkspaceId(): string | undefined {
  return useQuery(workspacesQuery).data?.[0]?.id;
}
