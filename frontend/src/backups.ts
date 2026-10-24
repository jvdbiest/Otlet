// SPDX-License-Identifier: AGPL-3.0-or-later
// Réglages › Sauvegardes (F08, ADR-0042), for the administrator of the instance.
import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, apiError, type components } from "./api/client.ts";

export type BackupsView = components["schemas"]["BackupsView"];
export type BackupView = components["schemas"]["BackupView"];
export type ScheduleView = components["schemas"]["ScheduleView"];

const KEY = ["admin", "backups"] as const;

/** The backups, their destination and schedule; followed every 5 s while one is asked for. */
export const backupsQuery = queryOptions({
  queryKey: KEY,
  queryFn: async (): Promise<BackupsView> => {
    const { data, error, response } = await api.GET("/api/admin/backups");
    if (data === undefined) {
      throw apiError(response, error);
    }
    return data;
  },
  refetchInterval: (query) => {
    const view = query.state.data;
    const busy =
      view?.state.running === true ||
      view?.request?.status === "pending" ||
      view?.request?.status === "running";
    return busy ? 5_000 : 60_000;
  },
});

export function useSaveSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (schedule: ScheduleView) => {
      const { data, error, response } = await api.PUT("/api/admin/backups/schedule", { body: schedule });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
  });
}

/** « Sauvegarder maintenant »: the backup service takes it within half a minute. */
export function useBackupNow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data, error, response } = await api.POST("/api/admin/backups/run");
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
  });
}

export function downloadUrl(name: string): string {
  return `/api/admin/backups/${encodeURIComponent(name)}/download`;
}
