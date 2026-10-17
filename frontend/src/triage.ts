// SPDX-License-Identifier: AGPL-3.0-or-later
// The watch feed of the user and its triage (X02): keep, dismiss, pin, read.
import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, apiError, type components } from "./api/client.ts";

export type FeedItemView = components["schemas"]["FeedItemView"];
export type TriageView = components["schemas"]["TriageView"];
export type TopicTagView = components["schemas"]["TopicTagView"];
export type ProgressView = components["schemas"]["ProgressView"];
export type FeedView = "to_sort" | "kept" | "pinned" | "dismissed" | "all";

export const FEED_PAGE_SIZE = 50;

/** Items dated from `since` (included) to `until` (excluded), ISO instants; null leaves a side open. */
export interface Period {
  since: string | null;
  until: string | null;
}

export const ANY_TIME: Period = { since: null, until: null };

export interface FeedFilter {
  view: FeedView;
  sourceId: string | null;
  unread: boolean;
  topicIds: string[];
  allTopics: boolean;
  period: Period;
}

export const feedQuery = (workspaceId: string, filter: FeedFilter, before: string | null) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "feed", filter, before],
    queryFn: async (): Promise<FeedItemView[]> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/feed", {
        params: {
          path: { workspace_id: workspaceId },
          query: {
            view: filter.view,
            unread: filter.unread,
            topic_id: filter.topicIds,
            all_topics: filter.allTopics,
            limit: FEED_PAGE_SIZE,
            ...(filter.sourceId ? { source_id: filter.sourceId } : {}),
            ...(before ? { before } : {}),
            ...(filter.period.since ? { since: filter.period.since } : {}),
            ...(filter.period.until ? { until: filter.period.until } : {}),
          },
        },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    refetchInterval: 60_000,
  });

export const progressQuery = (workspaceId: string) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "progress"],
    queryFn: async (): Promise<ProgressView> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/progress", {
        params: { path: { workspace_id: workspaceId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
  });

export const itemTriageQuery = (workspaceId: string, itemId: string) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "item", itemId, "triage"],
    queryFn: async (): Promise<TriageView> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/items/{item_id}/triage", {
        params: { path: { workspace_id: workspaceId, item_id: itemId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
  });

export interface TriageChange {
  decision?: "kept" | "dismissed" | null;
  pinned?: boolean;
  read?: boolean;
}

export function useChangeTriage(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ itemId, change }: { itemId: string; change: TriageChange }) => {
      const { data, error, response } = await api.PATCH("/api/workspaces/{workspace_id}/items/{item_id}/triage", {
        params: { path: { workspace_id: workspaceId, item_id: itemId } },
        body: change,
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspaces", workspaceId] }),
  });
}

export type BulkAction = "keep" | "dismiss" | "pin" | "to_sort";

/** One action for several items of the feed at once; answers how many changed. */
export function useBulkTriage(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ itemIds, action }: { itemIds: string[]; action: BulkAction }) => {
      const { data, error, response } = await api.POST("/api/workspaces/{workspace_id}/items/triage", {
        params: { path: { workspace_id: workspaceId } },
        body: { item_ids: itemIds, action },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data.changed;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspaces", workspaceId] }),
  });
}
