// SPDX-License-Identifier: AGPL-3.0-or-later
// The briefs of the workspace (U03): the instructions of an article, built on kept items.
import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, apiError, type components } from "./api/client.ts";

export type BriefView = components["schemas"]["BriefView"];
export type BriefBody = components["schemas"]["BriefBody"];
export type BriefLength = BriefView["length"];
export type BriefMode = BriefView["mode"];
export type BriefItemView = BriefView["items"][number];
export type VocabularyView = components["schemas"]["VocabularyView"];
export type ChoiceView = components["schemas"]["ChoiceView"];

/** The values of a brief's audience, tone and channel, each with its definition for the model. */
export const vocabularyQuery = (workspaceId: string) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "brief-vocabulary"],
    staleTime: Infinity,
    queryFn: async (): Promise<VocabularyView> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/brief-vocabulary", {
        params: { path: { workspace_id: workspaceId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
  });

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

export type DraftView = components["schemas"]["DraftView"];
export type VersionView = components["schemas"]["VersionView"];
export type GenerationView = components["schemas"]["GenerationView"];

/** The article of a brief and its latest generation, followed while a generation runs. */
export const draftQuery = (workspaceId: string, briefId: string) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "briefs", briefId, "draft"],
    queryFn: async (): Promise<DraftView> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/briefs/{brief_id}/draft", {
        params: { path: { workspace_id: workspaceId, brief_id: briefId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    // A local model may write for minutes: followed every three seconds until it ends.
    refetchInterval: (query) => (query.state.data?.generation?.status === "running" ? 3_000 : false),
  });

export function useGenerateDraft(workspaceId: string, briefId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data, error, response } = await api.POST(
        "/api/workspaces/{workspace_id}/briefs/{brief_id}/generations",
        { params: { path: { workspace_id: workspaceId, brief_id: briefId } } },
      );
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: draftQuery(workspaceId, briefId).queryKey }),
  });
}

/** Cancels the draft being written: nothing of it is kept. */
export function useCancelGeneration(workspaceId: string, briefId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { error, response } = await api.DELETE(
        "/api/workspaces/{workspace_id}/briefs/{brief_id}/generations/running",
        { params: { path: { workspace_id: workspaceId, brief_id: briefId } } },
      );
      if (!response.ok && response.status !== 404) {
        throw apiError(response, error);
      }
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: draftQuery(workspaceId, briefId).queryKey }),
  });
}

/** Empties the details and attempts of the drafts of a brief; the versions stay. */
export function useClearDetails(workspaceId: string, briefId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { error, response } = await api.DELETE("/api/workspaces/{workspace_id}/briefs/{brief_id}/details", {
        params: { path: { workspace_id: workspaceId, brief_id: briefId } },
      });
      if (!response.ok) {
        throw apiError(response, error);
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: draftQuery(workspaceId, briefId).queryKey }),
  });
}

export type SaveBody = components["schemas"]["SaveBody"];

/** Removes the copy « Modifier » made of a model's version, closed without a change. */
export function useDiscardVersion(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ articleId, number }: { articleId: string; number: number }) => {
      const { error, response } = await api.DELETE(
        "/api/workspaces/{workspace_id}/articles/{article_id}/versions/{number}",
        { params: { path: { workspace_id: workspaceId, article_id: articleId, number } } },
      );
      if (!response.ok) {
        throw apiError(response, error);
      }
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["workspaces", workspaceId] }),
  });
}

/** « Enregistrer » a version retouched in the editor, or « Enregistrer comme nouvelle version »
 * (ADR-0036): the version saved comes back, a new one when the version edited was the model's. */
export function useSaveVersion(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ articleId, number, body }: { articleId: string; number: number; body: SaveBody }) => {
      const { data, error, response } = await api.PUT(
        "/api/workspaces/{workspace_id}/articles/{article_id}/versions/{number}",
        { params: { path: { workspace_id: workspaceId, article_id: articleId, number } }, body },
      );
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspaces", workspaceId] }),
  });
}

export type ArticleView = components["schemas"]["ArticleView"];
export type LibraryEntryView = components["schemas"]["LibraryEntryView"];
export type ArticleStatus = ArticleView["status"];

/** The Library (X04): the articles sent to it, searched and filtered. */
export const libraryQuery = (workspaceId: string, q: string, archived: boolean, tag: string) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "library", q, archived, tag],
    queryFn: async (): Promise<LibraryEntryView[]> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/library", {
        params: {
          path: { workspace_id: workspaceId },
          query: { q, ...(archived ? { status: "archive" as const } : {}), ...(tag ? { tag } : {}) },
        },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
  });

export const libraryTagsQuery = (workspaceId: string) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "library-tags"],
    queryFn: async (): Promise<string[]> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/library/tags", {
        params: { path: { workspace_id: workspaceId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
  });

export const articleQuery = (workspaceId: string, articleId: string) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "articles", articleId],
    queryFn: async (): Promise<ArticleView> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/articles/{article_id}", {
        params: { path: { workspace_id: workspaceId, article_id: articleId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
  });

/** « Envoyer en Bibliothèque », or « Valider » a later version. */
export function useSendArticle(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ articleId, number }: { articleId: string; number: number }) => {
      const { data, error, response } = await api.POST("/api/workspaces/{workspace_id}/articles/{article_id}/send", {
        params: { path: { workspace_id: workspaceId, article_id: articleId } },
        body: { number },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspaces", workspaceId] }),
  });
}

export function useArchiveArticle(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ articleId, archived }: { articleId: string; archived: boolean }) => {
      const { data, error, response } = await api.POST(
        "/api/workspaces/{workspace_id}/articles/{article_id}/archive",
        { params: { path: { workspace_id: workspaceId, article_id: articleId } }, body: { archived } },
      );
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspaces", workspaceId] }),
  });
}

export function useSetTags(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ articleId, tags }: { articleId: string; tags: string[] }) => {
      const { data, error, response } = await api.PUT("/api/workspaces/{workspace_id}/articles/{article_id}/tags", {
        params: { path: { workspace_id: workspaceId, article_id: articleId } },
        body: { tags },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspaces", workspaceId] }),
  });
}
