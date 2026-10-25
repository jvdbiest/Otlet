// SPDX-License-Identifier: AGPL-3.0-or-later
// The Assistant de veille (A1b-1, ADR-0043): its dossiers, and the glossary of the workspace.
import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, apiError, type components } from "./api/client.ts";

export type DossierView = components["schemas"]["DossierView"];
export type DossierBody = components["schemas"]["DossierBody"];
export type DossierCandidate = DossierView["candidates"][number];
export type DossierSummaryView = components["schemas"]["DossierSummaryView"];
export type EntryView = components["schemas"]["EntryView"];

/** A dossier, read again every few seconds while the worker fills it. */
export const dossierQuery = (workspaceId: string, dossierId: string) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "assistant", "dossiers", dossierId],
    queryFn: async (): Promise<DossierView> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/assistant/dossiers/{dossier_id}", {
        params: { path: { workspace_id: workspaceId, dossier_id: dossierId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    refetchInterval: (query) => (query.state.data?.status === "done" ? false : 3000),
  });

export const dossiersQuery = (workspaceId: string) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "assistant", "dossiers"],
    queryFn: async (): Promise<DossierSummaryView[]> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/assistant/dossiers", {
        params: { path: { workspace_id: workspaceId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
  });

export function useStartDossier(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: DossierBody) => {
      const { data, error, response } = await api.POST("/api/workspaces/{workspace_id}/assistant/dossiers", {
        params: { path: { workspace_id: workspaceId } },
        body,
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: () => client.invalidateQueries({ queryKey: ["workspaces", workspaceId, "assistant", "dossiers"] }),
  });
}

export const glossaryQuery = (workspaceId: string) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "glossary"],
    queryFn: async (): Promise<EntryView[]> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/glossary", {
        params: { path: { workspace_id: workspaceId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
  });

/** Adds an entry, or replaces the terms of one (`entryId`). */
export function useSaveEntry(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ entryId, terms }: { entryId: string | null; terms: string[] }) => {
      const { data, error, response } =
        entryId === null
          ? await api.POST("/api/workspaces/{workspace_id}/glossary", {
              params: { path: { workspace_id: workspaceId } },
              body: { terms },
            })
          : await api.PUT("/api/workspaces/{workspace_id}/glossary/{entry_id}", {
              params: { path: { workspace_id: workspaceId, entry_id: entryId } },
              body: { terms },
            });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: () => client.invalidateQueries({ queryKey: ["workspaces", workspaceId, "glossary"] }),
  });
}

export function useDeleteEntry(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (entryId: string) => {
      const { error, response } = await api.DELETE("/api/workspaces/{workspace_id}/glossary/{entry_id}", {
        params: { path: { workspace_id: workspaceId, entry_id: entryId } },
      });
      if (!response.ok) {
        throw apiError(response, error);
      }
    },
    onSuccess: () => client.invalidateQueries({ queryKey: ["workspaces", workspaceId, "glossary"] }),
  });
}
