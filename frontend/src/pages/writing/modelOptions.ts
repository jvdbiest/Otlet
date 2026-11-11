// SPDX-License-Identifier: AGPL-3.0-or-later
// The models a user may choose for one task: a brief, or a writing language (docs/design/
// MODELE_PAR_LANGUE.md). Each option is « provider id|model ».
import { useQueries, useQuery } from "@tanstack/react-query";
import { catalogueQuery, installedQuery, profileQuery, providersQuery } from "../../ai.ts";

export interface ModelOption {
  value: string;
  label: string;
}

export function useModelOptions(current: readonly string[] = []): ModelOption[] {
  const providers = useQuery(providersQuery);
  const profile = useQuery(profileQuery);
  const catalogue = useQuery(catalogueQuery);
  const local = (providers.data ?? []).filter(
    (provider) => catalogue.data?.kinds.find((kind) => kind.name === provider.kind)?.custom_models === true,
  );
  const installed = useQueries({ queries: local.map((provider) => installedQuery(provider.id)) });
  const options: ModelOption[] = [];
  for (const provider of providers.data ?? []) {
    const engine = installed[local.findIndex((other) => other.id === provider.id)]?.data;
    const models = new Set(
      engine !== undefined
        ? engine.models.map((model) => model.name)
        : (catalogue.data?.models ?? [])
            .filter((model) => model.provider === provider.kind && model.status !== "blocked")
            .map((model) => model.model),
    );
    for (const entry of profile.data?.entries ?? []) {
      if (entry.provider_id === provider.id) {
        models.add(entry.model);
      }
    }
    for (const model of models) {
      options.push({ value: `${provider.id}|${model}`, label: `${provider.name} · ${model}` });
    }
  }
  for (const value of current) {
    if (value !== "" && !options.some((option) => option.value === value)) {
      options.push({ value, label: value.split("|", 2)[1] ?? value });
    }
  }
  return options;
}

/** The model part of « provider id|model ». */
export function modelName(value: string): string {
  return value.split("|", 2)[1] ?? value;
}
