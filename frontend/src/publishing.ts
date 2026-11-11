// SPDX-License-Identifier: AGPL-3.0-or-later
// Publishing (U07): the WordPress sites of the workspace, and the sends of an article, as a draft
// or published. The API records; the worker sends.
import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, apiError, type components } from "./api/client.ts";

export type SiteView = components["schemas"]["SiteView"];
export type SiteBody = components["schemas"]["SiteBody"];
export type PublicationView = components["schemas"]["PublicationView"];
export type PublicationBody = components["schemas"]["PublicationBody"];
export type EventView = components["schemas"]["EventView"];

const key = (workspaceId: string) => ["workspaces", workspaceId, "publishing"] as const;

/** The sites; refreshed while a « Tester » is under way. */
export const sitesQuery = (workspaceId: string) =>
  queryOptions({
    queryKey: [...key(workspaceId), "sites"],
    refetchInterval: (query) => ((query.state.data ?? []).some((s) => s.check_pending) ? 2000 : false),
    queryFn: async (): Promise<SiteView[]> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/publishing/sites", {
        params: { path: { workspace_id: workspaceId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
  });

/** The sends of an article, one per site; refreshed while one is under way. */
export const publicationsQuery = (workspaceId: string, articleId: string) =>
  queryOptions({
    queryKey: [...key(workspaceId), "articles", articleId],
    refetchInterval: (query) => ((query.state.data ?? []).some((p) => p.state === "pending") ? 2000 : false),
    queryFn: async (): Promise<PublicationView[]> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/articles/{article_id}/publications", {
        params: { path: { workspace_id: workspaceId, article_id: articleId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
  });

export const eventsQuery = (workspaceId: string, publicationId: string) =>
  queryOptions({
    queryKey: [...key(workspaceId), "events", publicationId],
    queryFn: async (): Promise<EventView[]> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/publications/{publication_id}/events", {
        params: { path: { workspace_id: workspaceId, publication_id: publicationId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
  });

function useRefresh(workspaceId: string) {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: key(workspaceId) });
}

export function useAddSite(workspaceId: string) {
  const refresh = useRefresh(workspaceId);
  return useMutation({
    mutationFn: async (body: SiteBody) => {
      const { data, error, response } = await api.POST("/api/workspaces/{workspace_id}/publishing/sites", {
        params: { path: { workspace_id: workspaceId } },
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

export function useUpdateSite(workspaceId: string) {
  const refresh = useRefresh(workspaceId);
  return useMutation({
    mutationFn: async ({ siteId, body }: { siteId: string; body: SiteBody }) => {
      const { data, error, response } = await api.PUT("/api/workspaces/{workspace_id}/publishing/sites/{site_id}", {
        params: { path: { workspace_id: workspaceId, site_id: siteId } },
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

export function useDeleteSite(workspaceId: string) {
  const refresh = useRefresh(workspaceId);
  return useMutation({
    mutationFn: async (siteId: string) => {
      const { error, response } = await api.DELETE("/api/workspaces/{workspace_id}/publishing/sites/{site_id}", {
        params: { path: { workspace_id: workspaceId, site_id: siteId } },
      });
      if (!response.ok) {
        throw apiError(response, error);
      }
    },
    onSuccess: refresh,
  });
}

export function useCheckSite(workspaceId: string) {
  const refresh = useRefresh(workspaceId);
  return useMutation({
    mutationFn: async (siteId: string) => {
      const { data, error, response } = await api.POST("/api/workspaces/{workspace_id}/publishing/sites/{site_id}/check", {
        params: { path: { workspace_id: workspaceId, site_id: siteId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: refresh,
  });
}

export function useSendToSite(workspaceId: string) {
  const refresh = useRefresh(workspaceId);
  return useMutation({
    mutationFn: async ({ articleId, body }: { articleId: string; body: PublicationBody }) => {
      const { data, error, response } = await api.POST("/api/workspaces/{workspace_id}/articles/{article_id}/publications", {
        params: { path: { workspace_id: workspaceId, article_id: articleId } },
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
