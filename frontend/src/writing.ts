// SPDX-License-Identifier: AGPL-3.0-or-later
// The briefs of the workspace (U03): the instructions of an article, built on kept items.
import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, apiError, type components } from "./api/client.ts";

export type BriefView = components["schemas"]["BriefView"];
export type BriefBody = components["schemas"]["BriefBody"];
export type BriefLength = BriefView["length"];

export const briefsQuery = (workspaceId: string) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "briefs"],
    queryFn: async (): Promise<BriefView[]> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/briefs", {
        params: { path: { workspace_id: workspaceId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
  });

export const briefQuery = (workspaceId: string, briefId: string) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "briefs", briefId],
    queryFn: async (): Promise<BriefView> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/briefs/{brief_id}", {
        params: { path: { workspace_id: workspaceId, brief_id: briefId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
  });

// A brief changes the triage of its items: the whole workspace is refreshed.
function useRefresh(workspaceId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["workspaces", workspaceId] });
}

export function useSaveBrief(workspaceId: string) {
  const refresh = useRefresh(workspaceId);
  return useMutation({
    mutationFn: async ({ briefId, body }: { briefId: string | null; body: BriefBody }) => {
      const { data, error, response } =
        briefId === null
          ? await api.POST("/api/workspaces/{workspace_id}/briefs", {
              params: { path: { workspace_id: workspaceId } },
              body,
            })
          : await api.PUT("/api/workspaces/{workspace_id}/briefs/{brief_id}", {
              params: { path: { workspace_id: workspaceId, brief_id: briefId } },
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

export function useDeleteBrief(workspaceId: string) {
  const refresh = useRefresh(workspaceId);
  return useMutation({
    mutationFn: async (briefId: string) => {
      const { error, response } = await api.DELETE("/api/workspaces/{workspace_id}/briefs/{brief_id}", {
        params: { path: { workspace_id: workspaceId, brief_id: briefId } },
      });
      if (!response.ok) {
        throw apiError(response, error);
      }
    },
    onSuccess: refresh,
  });
}
