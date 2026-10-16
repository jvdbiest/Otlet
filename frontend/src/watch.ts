// SPDX-License-Identifier: AGPL-3.0-or-later
// Topics, their scored items, the search and the same story elsewhere (U02).
import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, apiError, type components } from "./api/client.ts";

export type TopicView = components["schemas"]["TopicView"];
export type ScoredItemView = components["schemas"]["ScoredItemView"];
export type ContributionView = components["schemas"]["ContributionView"];
export type FoundItemView = components["schemas"]["FoundItemView"];
export type ItemWatchView = components["schemas"]["ItemWatchView"];
export type TopicBody = components["schemas"]["TopicBody"];

export const TOPIC_PAGE_SIZE = 50;

export const topicsQuery = (workspaceId: string) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "topics"],
    queryFn: async (): Promise<TopicView[]> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/topics", {
        params: { path: { workspace_id: workspaceId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    // While a topic is matched again, its state is followed closely.
    refetchInterval: (query) => (query.state.data?.some((topic) => topic.rescoring) ? 2_000 : false),
  });

export const topicQuery = (workspaceId: string, topicId: string) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "topics", topicId],
    queryFn: async (): Promise<TopicView> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/topics/{topic_id}", {
        params: { path: { workspace_id: workspaceId, topic_id: topicId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    refetchInterval: (query) => (query.state.data?.rescoring ? 2_000 : false),
  });

export const topicItemsQuery = (workspaceId: string, topicId: string, offset: number) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "topics", topicId, "items", offset],
    queryFn: async (): Promise<ScoredItemView[]> => {
      const { data, error, response } = await api.GET(
        "/api/workspaces/{workspace_id}/topics/{topic_id}/items",
        {
          params: {
            path: { workspace_id: workspaceId, topic_id: topicId },
            query: { limit: TOPIC_PAGE_SIZE, offset },
          },
        },
      );
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    // A new or changed topic is matched in the background: its list fills in by itself.
    refetchInterval: 10_000,
  });

export const itemWatchQuery = (workspaceId: string, itemId: string) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "item", itemId, "watch"],
    queryFn: async (): Promise<ItemWatchView> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/items/{item_id}/watch", {
        params: { path: { workspace_id: workspaceId, item_id: itemId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
  });

export const searchQuery = (workspaceId: string, q: string) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "search", q],
    queryFn: async (): Promise<FoundItemView[]> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/search", {
        params: { path: { workspace_id: workspaceId }, query: { q, limit: 50 } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    enabled: q.trim() !== "",
  });

function useRefresh(workspaceId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["workspaces", workspaceId] });
}

export function useSaveTopic(workspaceId: string) {
  const refresh = useRefresh(workspaceId);
  return useMutation({
    mutationFn: async ({ topicId, body }: { topicId: string | null; body: TopicBody }) => {
      const result =
        topicId === null
          ? await api.POST("/api/workspaces/{workspace_id}/topics", {
              params: { path: { workspace_id: workspaceId } },
              body,
            })
          : await api.PUT("/api/workspaces/{workspace_id}/topics/{topic_id}", {
              params: { path: { workspace_id: workspaceId, topic_id: topicId } },
              body,
            });
      if (result.data === undefined) {
        throw apiError(result.response, result.error);
      }
      return result.data;
    },
    onSuccess: refresh,
  });
}

export function useDeleteTopic(workspaceId: string) {
  const refresh = useRefresh(workspaceId);
  return useMutation({
    mutationFn: async (topicId: string) => {
      const { error, response } = await api.DELETE("/api/workspaces/{workspace_id}/topics/{topic_id}", {
        params: { path: { workspace_id: workspaceId, topic_id: topicId } },
      });
      if (!response.ok) {
        throw apiError(response, error);
      }
    },
    onSuccess: refresh,
  });
}

export function useRescoreTopic(workspaceId: string) {
  const refresh = useRefresh(workspaceId);
  return useMutation({
    mutationFn: async (topicId: string) => {
      const { error, response } = await api.POST("/api/workspaces/{workspace_id}/topics/{topic_id}/rescore", {
        params: { path: { workspace_id: workspaceId, topic_id: topicId } },
      });
      if (!response.ok) {
        throw apiError(response, error);
      }
    },
    onSuccess: refresh,
  });
}

export function useRefreshWatch(workspaceId: string) {
  const refresh = useRefresh(workspaceId);
  return useMutation({
    mutationFn: async () => {
      const { data, error, response } = await api.POST("/api/workspaces/{workspace_id}/refresh", {
        params: { path: { workspace_id: workspaceId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: refresh,
  });
}
