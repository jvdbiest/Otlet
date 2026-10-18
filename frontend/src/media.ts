// SPDX-License-Identifier: AGPL-3.0-or-later
// The images of the workspace (X03b): imported from the editor, shown by their address.
import { api, apiError, type components } from "./api/client.ts";

export type MediaView = components["schemas"]["MediaView"];

/** Images the editor accepts; the server checks them again by decoding them. */
export const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"] as const;

/** The address of an image of the workspace. */
export function mediaUrl(workspaceId: string, mediaId: string): string {
  return `/api/workspaces/${encodeURIComponent(workspaceId)}/media/${encodeURIComponent(mediaId)}`;
}

/** The id of an image of Otlet from its address, if it is one. */
export function mediaIdOf(src: string): string | null {
  const found = /\/api\/workspaces\/[^/]+\/media\/([0-9a-f-]{36})$/.exec(src);
  return found?.[1] ?? null;
}

/** Sends an image as it is (the body is the file); its id and size come back. */
export async function uploadImage(workspaceId: string, file: Blob): Promise<MediaView> {
  const { data, error, response } = await api.POST("/api/workspaces/{workspace_id}/media", {
    params: { path: { workspace_id: workspaceId } },
    body: file as unknown as string,
    bodySerializer: (body) => body,
    headers: { "Content-Type": file.type || "application/octet-stream" },
  });
  if (data === undefined) {
    throw apiError(response, error);
  }
  return data;
}
