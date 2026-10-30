// SPDX-License-Identifier: AGPL-3.0-or-later
// The AI work under way for the user, in every module (Joël, 2026-10-30).
import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, apiError, type components } from "./api/client.ts";

export type AiTaskView = components["schemas"]["AiTaskView"];

export const aiTasksQuery = (workspaceId: string) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "ai-tasks"],
    queryFn: async (): Promise<AiTaskView[]> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/ai-tasks", {
        params: { path: { workspace_id: workspaceId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    refetchInterval: 3000,
  });

export function useCancelAllAiTasks(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data, error, response } = await api.POST("/api/workspaces/{workspace_id}/ai-tasks/cancel", {
        params: { path: { workspace_id: workspaceId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: () => client.invalidateQueries({ queryKey: ["workspaces", workspaceId] }),
  });
}
