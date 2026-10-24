// SPDX-License-Identifier: AGPL-3.0-or-later
// The briefs of the workspace (U03): the instructions of an article, built on kept items.
import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, apiError, type components } from "./api/client.ts";

export type BriefView = components["schemas"]["BriefView"];
export type BriefBody = components["schemas"]["BriefBody"];
export type BriefLength = BriefView["length"];
export type BriefMode = BriefView["mode"];
export type BriefNature = BriefView["nature"];
export type MatterBody = components["schemas"]["MatterBody"];
export type MatterView = components["schemas"]["MatterView"];
export type BriefItemView = BriefView["items"][number];
export type SourceTextView = components["schemas"]["SourceTextView"];

/** The texts of a brief's sources as the drafts receive them: the reference of « Comparer ». */
export const briefSourcesQuery = (workspaceId: string, briefId: string) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "briefs", briefId, "sources"],
    queryFn: async (): Promise<SourceTextView[]> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/briefs/{brief_id}/sources", {
        params: { path: { workspace_id: workspaceId, brief_id: briefId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
  });
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

/** The matter of a brief as it is being written (ADR-0041): computed by the server at each
 * change of its items, length, mode or nature; never stored. */
export const matterQuery = (workspaceId: string, body: MatterBody) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "brief-matter", body],
    queryFn: async (): Promise<MatterView> => {
      const { data, error, response } = await api.POST("/api/workspaces/{workspace_id}/briefs/matter", {
        params: { path: { workspace_id: workspaceId } },
        body,
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
  });

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
    // `force`: « Générer quand même », the sources being too thin (Joël, 2026-10-19).
    mutationFn: async (force: boolean) => {
      const { data, error, response } = await api.POST(
        "/api/workspaces/{workspace_id}/briefs/{brief_id}/generations",
        { params: { path: { workspace_id: workspaceId, brief_id: briefId } }, body: { force } },
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
export const libraryQuery = (workspaceId: string, q: string, archived: boolean, tag: string, topicId = "") =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "library", q, archived, tag, topicId],
    queryFn: async (): Promise<LibraryEntryView[]> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/library", {
        params: {
          path: { workspace_id: workspaceId },
          query: {
            q,
            ...(archived ? { status: "archive" as const } : {}),
            ...(tag ? { tag } : {}),
            ...(topicId ? { topic_id: topicId } : {}),
          },
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

/** The topics of the Library's articles: those of the items of their briefs (Joël, 2026-10-20). */
export const libraryTopicsQuery = (workspaceId: string) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "library-topics"],
    queryFn: async (): Promise<{ id: string; name: string }[]> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/library/topics", {
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
/** An article written by hand, without a brief: in the Library at once (Joël, 2026-10-20). */
export function useCreateArticle(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (title: string) => {
      const { data, error, response } = await api.POST("/api/workspaces/{workspace_id}/articles", {
        params: { path: { workspace_id: workspaceId } },
        body: { title },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspaces", workspaceId] }),
  });
}

/** « Dupliquer »: a new article, without a brief, from a copy of a version. */
export function useDuplicateArticle(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ articleId, number }: { articleId: string; number: number }) => {
      const { data, error, response } = await api.POST(
        "/api/workspaces/{workspace_id}/articles/{article_id}/duplicate",
        { params: { path: { workspace_id: workspaceId, article_id: articleId } }, body: { number } },
      );
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspaces", workspaceId] }),
  });
}

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

export type LibraryAction = "archive" | "unarchive" | "duplicate" | "delete";
export type ExportKind = "pdf" | "docx" | "html" | "md" | "txt";

/** An action on the articles chosen in the Library (Joël, 2026-10-20): what was done, and what
 * could not be, with why. Deleting takes archived articles only. */
export function useLibraryAction(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ action, articleIds }: { action: LibraryAction; articleIds: string[] }) => {
      const path = { params: { path: { workspace_id: workspaceId } } };
      const answer =
        action === "archive" || action === "unarchive"
          ? await api.POST("/api/workspaces/{workspace_id}/library/archive", {
              ...path,
              body: { article_ids: articleIds, archived: action === "archive" },
            })
          : action === "duplicate"
            ? await api.POST("/api/workspaces/{workspace_id}/library/duplicate", {
                ...path,
                body: { article_ids: articleIds },
              })
            : await api.POST("/api/workspaces/{workspace_id}/library/delete", {
                ...path,
                body: { article_ids: articleIds },
              });
      if (answer.data === undefined) {
        throw apiError(answer.response, answer.error);
      }
      return answer.data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspaces", workspaceId] }),
  });
}

/** The articles chosen in one ZIP, a file each: the validated version, else the latest. */
export async function exportSelection(workspaceId: string, articleIds: string[], kind: ExportKind): Promise<Blob> {
  const { data, error, response } = await api.POST("/api/workspaces/{workspace_id}/library/export", {
    params: { path: { workspace_id: workspaceId } },
    body: { article_ids: articleIds, kind },
    parseAs: "blob",
  });
  if (data === undefined) {
    throw apiError(response, error);
  }
  return data;
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
