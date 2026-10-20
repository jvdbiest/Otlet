// SPDX-License-Identifier: AGPL-3.0-or-later
// The images of the workspace (X03b): imported from the editor, shown by their address.
import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, apiError, type components } from "./api/client.ts";

export type MediaView = components["schemas"]["MediaView"];
export type MediaEntryView = components["schemas"]["MediaEntryView"];
export type MediaDetailsView = components["schemas"]["MediaDetailsView"];
export type MediaSection = "articles" | "bank";

/** Images the editor accepts; the server checks them again by decoding them. */
export const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"] as const;

/** The address of an image of the workspace. */
export function mediaUrl(workspaceId: string, mediaId: string): string {
  return `/api/workspaces/${encodeURIComponent(workspaceId)}/media/${encodeURIComponent(mediaId)}`;
}

/** The small image of the médiathèque's grid (ADR-0040), never the original. */
export function thumbnailUrl(workspaceId: string, mediaId: string): string {
  return `${mediaUrl(workspaceId, mediaId)}/thumbnail`;
}

/** The id of an image of Otlet from its address, if it is one. */
export function mediaIdOf(src: string): string | null {
  const found = /\/api\/workspaces\/[^/]+\/media\/([0-9a-f-]{36})$/.exec(src);
  return found?.[1] ?? null;
}

/** Sends an image as it is (the body is the file); its id and size come back. Its file's name
 * names it; `bank`: imported into the bank of images. */
export async function uploadImage(workspaceId: string, file: Blob, bank = false): Promise<MediaView> {
  const name = file instanceof File && file.name ? file.name.replace(/\.[a-z0-9]{1,5}$/i, "") : undefined;
  const { data, error, response } = await api.POST("/api/workspaces/{workspace_id}/media", {
    params: {
      path: { workspace_id: workspaceId },
      query: { ...(name ? { name } : {}), ...(bank ? { bank } : {}) },
    },
    body: file as unknown as string,
    bodySerializer: (body) => body,
    headers: { "Content-Type": file.type || "application/octet-stream" },
  });
  if (data === undefined) {
    throw apiError(response, error);
  }
  return data;
}

/** The images of a section of the médiathèque, newest first (ADR-0040). */
export const mediaListQuery = (
  workspaceId: string,
  section: MediaSection,
  q: string,
  used: boolean | null,
  tag = "",
) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "media", section, q, used, tag],
    queryFn: async (): Promise<MediaEntryView[]> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/media", {
        params: {
          path: { workspace_id: workspaceId },
          query: { view: section, q, ...(used === null ? {} : { used }), ...(tag ? { tag } : {}) },
        },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
  });

/** An image and the articles that show it. */
export const mediaDetailsQuery = (workspaceId: string, mediaId: string) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "media-details", mediaId],
    queryFn: async (): Promise<MediaDetailsView> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/media/{media_id}/details", {
        params: { path: { workspace_id: workspaceId, media_id: mediaId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
  });

/** The tags of the images of the workspace. */
export const mediaTagsQuery = (workspaceId: string) =>
  queryOptions({
    queryKey: ["workspaces", workspaceId, "media-tags"],
    queryFn: async (): Promise<string[]> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/media/tags", {
        params: { path: { workspace_id: workspaceId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
  });

export function useSetMediaTags(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ mediaId, tags }: { mediaId: string; tags: string[] }) => {
      const { data, error, response } = await api.PUT("/api/workspaces/{workspace_id}/media/{media_id}/tags", {
        params: { path: { workspace_id: workspaceId, media_id: mediaId } },
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

export interface MediaDescription {
  name: string;
  description: string;
  credit: string;
  licence: string;
  source_url: string;
}

export function useDescribeMedia(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ mediaId, description }: { mediaId: string; description: MediaDescription }) => {
      const { data, error, response } = await api.PATCH("/api/workspaces/{workspace_id}/media/{media_id}", {
        params: { path: { workspace_id: workspaceId, media_id: mediaId } },
        body: description,
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspaces", workspaceId] }),
  });
}

export type MediaAction = "keep" | "unkeep" | "delete";

/** An action on the images chosen: into the bank, out of it, or deleted (those no article
 * shows); what was done, and what was refused, with why. */
export function useMediaAction(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ action, mediaIds }: { action: MediaAction; mediaIds: string[] }) => {
      const path = { params: { path: { workspace_id: workspaceId } } };
      const answer =
        action === "delete"
          ? await api.POST("/api/workspaces/{workspace_id}/media/delete", { ...path, body: { media_ids: mediaIds } })
          : await api.POST("/api/workspaces/{workspace_id}/media/bank", {
              ...path,
              body: { media_ids: mediaIds, in_bank: action === "keep" },
            });
      if (answer.data === undefined) {
        throw apiError(answer.response, answer.error);
      }
      return answer.data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspaces", workspaceId] }),
  });
}
