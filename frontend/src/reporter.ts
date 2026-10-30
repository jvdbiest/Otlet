// SPDX-License-Identifier: AGPL-3.0-or-later
// The Reporter (A2-1, ADR-0044): conversations whose answers are sets of items and lines of fact.
import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, apiError, type components } from "./api/client.ts";

export type ConversationView = components["schemas"]["ConversationView"];
export type ConversationSummaryView = components["schemas"]["ConversationSummaryView"];
export type TurnView = components["schemas"]["TurnView"];
export type TurnCandidate = TurnView["candidates"][number];
export type FactView = components["schemas"]["FactView"];
export type ReadingView = components["schemas"]["ReadingView"];
/** A question, read by the model before its answer is shown when `read` (« Lire avant de répondre »). */
export type Question =
  | string
  | { question: string; read: boolean; date_from?: string | null; date_to?: string | null };

const body = (input: Question) => (typeof input === "string" ? { question: input, read: false } : input);
export type ConceptBody = components["schemas"]["ConceptBody"];

const key = (workspaceId: string) => ["workspaces", workspaceId, "reporter"] as const;

/** A conversation, read again every few seconds while the worker answers a question. */
export const conversationQuery = (workspaceId: string, conversationId: string) =>
  queryOptions({
    queryKey: [...key(workspaceId), conversationId],
    queryFn: async (): Promise<ConversationView> => {
      const { data, error, response } = await api.GET(
        "/api/workspaces/{workspace_id}/reporter/conversations/{conversation_id}",
        { params: { path: { workspace_id: workspaceId, conversation_id: conversationId } } },
      );
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    refetchInterval: (query) => (query.state.data?.turns.some((t) => t.status === "pending") === true ? 2000 : false),
  });

export const conversationsQuery = (workspaceId: string) =>
  queryOptions({
    queryKey: [...key(workspaceId), "list"],
    queryFn: async (): Promise<ConversationSummaryView[]> => {
      const { data, error, response } = await api.GET("/api/workspaces/{workspace_id}/reporter/conversations", {
        params: { path: { workspace_id: workspaceId } },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
  });

export function useStartConversation(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (question: Question) => {
      const { data, error, response } = await api.POST("/api/workspaces/{workspace_id}/reporter/conversations", {
        params: { path: { workspace_id: workspaceId } },
        body: body(question),
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: () => client.invalidateQueries({ queryKey: [...key(workspaceId), "list"] }),
  });
}

export function useAsk(workspaceId: string, conversationId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (question: Question) => {
      const { data, error, response } = await api.POST(
        "/api/workspaces/{workspace_id}/reporter/conversations/{conversation_id}/turns",
        { params: { path: { workspace_id: workspaceId, conversation_id: conversationId } }, body: body(question) },
      );
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: () => client.invalidateQueries({ queryKey: [...key(workspaceId), conversationId] }),
  });
}

/** Ends the question being answered; the worker cuts its call to the model. */
export function useCancelQuestion(workspaceId: string, conversationId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data, error, response } = await api.POST(
        "/api/workspaces/{workspace_id}/reporter/conversations/{conversation_id}/cancel",
        { params: { path: { workspace_id: workspaceId, conversation_id: conversationId } } },
      );
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: () => client.invalidateQueries({ queryKey: ["workspaces", workspaceId] }),
  });
}

/** A fact read further: the next items of the set; the worker adds their lines. */
export function useReadMore(workspaceId: string, conversationId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (turnId: string) => {
      const { data, error, response } = await api.POST(
        "/api/workspaces/{workspace_id}/reporter/conversations/{conversation_id}/turns/{turn_id}/more",
        { params: { path: { workspace_id: workspaceId, conversation_id: conversationId, turn_id: turnId } } },
      );
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: () => client.invalidateQueries({ queryKey: [...key(workspaceId), conversationId] }),
  });
}

/** « Vérifier en lisant »: the model reads the set of an answered question, once. */
export function useReadSet(workspaceId: string, conversationId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (turnId: string) => {
      const { data, error, response } = await api.POST(
        "/api/workspaces/{workspace_id}/reporter/conversations/{conversation_id}/turns/{turn_id}/reading",
        { params: { path: { workspace_id: workspaceId, conversation_id: conversationId, turn_id: turnId } } },
      );
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: () => client.invalidateQueries({ queryKey: [...key(workspaceId), conversationId] }),
  });
}

/** The author's terms for the last set: found again at once, without a model. */
export function useSetTerms(workspaceId: string, conversationId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ turnId, concepts }: { turnId: string; concepts: ConceptBody[] }) => {
      const { data, error, response } = await api.PUT(
        "/api/workspaces/{workspace_id}/reporter/conversations/{conversation_id}/turns/{turn_id}/terms",
        {
          params: { path: { workspace_id: workspaceId, conversation_id: conversationId, turn_id: turnId } },
          body: { concepts },
        },
      );
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: () => client.invalidateQueries({ queryKey: [...key(workspaceId), conversationId] }),
  });
}
