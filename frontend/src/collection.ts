// SPDX-License-Identifier: AGPL-3.0-or-later
// Sources and the items they bring (U01), cached by TanStack Query. Every call goes to the
// single workspace of the user (É1, ROADMAP §5.2).
import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, apiError, type components } from "./api/client.ts";

export type SourceView = components["schemas"]["SourceView"];
export type ItemView = components["schemas"]["ItemView"];
export type CheckView = components["schemas"]["CheckView"];

// While a source waits for its first run or items wait to be read, the lists refresh by
// themselves; otherwise at this pace.
const LIVE_REFRESH_MS = 5_000;
const IDLE_REFRESH_MS = 60_000;
export const PAGE_SIZE = 50;

function path(workspaceId: string) {
  return { path: { workspace_id: workspaceId } };
}

export const sourcesQuery = (workspaceId: string) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "sources"],
    queryFn: async (): Promise<SourceView[]> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/sources", {
        params: path(workspaceId),
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    refetchInterval: (query) =>
      query.state.data?.some((source) => source.last_fetched_at === null && source.active)
        ? LIVE_REFRESH_MS
        : IDLE_REFRESH_MS,
  });

export const itemsQuery = (workspaceId: string, sourceId: string | null, before: string | null) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "items", { sourceId, before }],
    queryFn: async (): Promise<ItemView[]> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/items", {
        params: {
          ...path(workspaceId),
          query: { limit: PAGE_SIZE, ...(sourceId ? { source_id: sourceId } : {}), ...(before ? { before } : {}) },
        },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    refetchInterval: (query) =>
      query.state.data?.some((item) => item.text_status === "pending") ? LIVE_REFRESH_MS : IDLE_REFRESH_MS,
  });

export const itemQuery = (workspaceId: string, itemId: string) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "item", itemId],
    queryFn: async (): Promise<ItemView> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/items/{item_id}", {
        params: { path: { workspace_id: workspaceId, item_id: itemId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    refetchInterval: (query) => (query.state.data?.text_status === "pending" ? LIVE_REFRESH_MS : false),
  });

export const checksQuery = (workspaceId: string, sourceId: string) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "sources", sourceId, "checks"],
    queryFn: async (): Promise<CheckView[]> => {
      const { data, error, response } = await api.GET(
        "/api/workspaces/{workspace_id}/sources/{source_id}/checks",
        { params: { path: { workspace_id: workspaceId, source_id: sourceId } } },
      );
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
  });

/** Refreshes everything the collection shows after a change. */
function useRefresh(workspaceId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["workspaces", workspaceId] });
}

export function useAddSource(workspaceId: string) {
  const refresh = useRefresh(workspaceId);
  return useMutation({
    mutationFn: async (body: { url: string; name?: string; interval_minutes: number }) => {
      const { data, error, response } = await api.POST("/api/workspaces/{workspace_id}/sources", {
        params: path(workspaceId),
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

export function useUpdateSource(workspaceId: string) {
  const refresh = useRefresh(workspaceId);
  return useMutation({
    mutationFn: async ({ sourceId, ...body }: { sourceId: string; active?: boolean; interval_minutes?: number }) => {
      const { data, error, response } = await api.PATCH("/api/workspaces/{workspace_id}/sources/{source_id}", {
        params: { path: { workspace_id: workspaceId, source_id: sourceId } },
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

export function useDeleteSource(workspaceId: string) {
  const refresh = useRefresh(workspaceId);
  return useMutation({
    mutationFn: async (sourceId: string) => {
      const { error, response } = await api.DELETE("/api/workspaces/{workspace_id}/sources/{source_id}", {
        params: { path: { workspace_id: workspaceId, source_id: sourceId } },
      });
      if (!response.ok) {
        throw apiError(response, error);
      }
    },
    onSuccess: refresh,
  });
}

export function useCollectNow(workspaceId: string) {
  const refresh = useRefresh(workspaceId);
  return useMutation({
    mutationFn: async (sourceId: string) => {
      const { error, response } = await api.POST("/api/workspaces/{workspace_id}/sources/{source_id}/collect", {
        params: { path: { workspace_id: workspaceId, source_id: sourceId } },
      });
      if (!response.ok) {
        throw apiError(response, error);
      }
    },
    onSuccess: refresh,
  });
}

export function useAddManualUrl(workspaceId: string) {
  const refresh = useRefresh(workspaceId);
  return useMutation({
    mutationFn: async (url: string) => {
      const { data, error, response } = await api.POST("/api/workspaces/{workspace_id}/items/manual-url", {
        params: path(workspaceId),
        body: { url },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: refresh,
  });
}

export interface ManualText {
  title: string;
  text: string;
  url?: string;
  declared_origin: string;
  usage_right: string;
}

export function useAddManualText(workspaceId: string) {
  const refresh = useRefresh(workspaceId);
  return useMutation({
    mutationFn: async (body: ManualText) => {
      const { data, error, response } = await api.POST("/api/workspaces/{workspace_id}/items/manual-text", {
        params: path(workspaceId),
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


/** Removes an item from the watch of the whole workspace, for good, with its text. */
export function useRemoveItem(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (itemId: string) => {
      const { error, response } = await api.DELETE("/api/workspaces/{workspace_id}/items/{item_id}", {
        params: { path: { workspace_id: workspaceId, item_id: itemId } },
      });
      if (!response.ok) {
        throw apiError(response, error);
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspaces", workspaceId] }),
  });
}
