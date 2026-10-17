// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import {
  budgetQuery,
  installedQuery,
  pullQuery,
  callsQuery,
  catalogueQuery,
  checkQuery,
  policyQuery,
  profileQuery,
  providersQuery,
  useAddProvider,
  useDeleteProvider,
  useSaveBudget,
  useSavePolicy,
  useSaveProfile,
  useStartCheck,
  useClearCalls,
  useSetContextWindow,
  useStartPull,
  type CatalogueView,
  type ProviderView,
} from "../../ai.ts";
import { ApiError } from "../../api/client.ts";
import { sessionQuery } from "../../session.ts";
import { errorText, formatDate } from "../watch/labels.ts";
import { styles } from "../watch/styles.ts";

/** Réglages > IA (F05, ADR-0027): the user chooses providers and models, sets a budget, tests
 * the profile; the administrator of the instance allows or blocks. */
export function AiSettingsPage() {
  const { t } = useTranslation();
  const catalogue = useQuery(catalogueQuery);
  const session = useQuery(sessionQuery);
  if (catalogue.data === undefined) {
    return <p>{t("app.loading")}</p>;
  }
  return (
    <div className={styles.article}>
      <h1>{t("ai.title")}</h1>
      <p className={styles.help}>{t("ai.intro")}</p>
      <Providers catalogue={catalogue.data} />
      <Profile catalogue={catalogue.data} />
      <Budget />
      <Check />
      {session.data?.user.is_instance_admin === true && <Policy catalogue={catalogue.data} />}
      <Journal />
    </div>
  );
}

const AI_ERRORS = [
  "address_not_allowed",
  "admin_only",
  "duplicate_model",
  "engine_unreachable",
  "install_not_allowed",
  "invalid_model_name",
  "not_a_local_engine",
  "invalid_context_window",
  "invalid_endpoint",
  "invalid_key",
  "invalid_name",
  "invalid_network",
  "invalid_port",
  "key_required",
  "model_blocked",
  "name_taken",
  "profile_too_long",
  "unknown_kind",
  "unknown_model",
  "unknown_provider",
] as const;
const FAILURES = [
  "no_profile",
  "budget",
  "refused",
  "invalid",
  "out_of_room",
  "quota",
  "unavailable",
  "blocked",
] as const;
const RESULTS = ["ok", "quota", "unavailable", "refused", "blocked", "budget", "invalid"] as const;

function among<T extends string>(list: readonly T[], value: string): value is T {
  return (list as readonly string[]).includes(value);
}

function errorOf(t: TFunction, error: Error | null): string | null {
  if (error === null) {
    return null;
  }
  if (error instanceof ApiError && error.detail !== null && among(AI_ERRORS, error.detail)) {
    return t(`ai.errors.${error.detail}`);
  }
  return errorText(t, error);
}

function resultText(t: TFunction, result: string): string {
  return among(RESULTS, result) ? t(`ai.result.${result}`) : result;
}

function Providers({ catalogue }: { catalogue: CatalogueView }) {
  const { t } = useTranslation();
  const providers = useQuery(providersQuery);
  const add = useAddProvider();
  const remove = useDeleteProvider();
  const [kind, setKind] = useState(catalogue.kinds[0]?.name ?? "");
  const chosen = catalogue.kinds.find((k) => k.name === kind);
  const [name, setName] = useState("");
  const [endpoint, setEndpoint] = useState(chosen?.endpoint ?? "");
  const [key, setKey] = useState("");
  return (
    <section className={styles.panel} aria-labelledby="ai-providers">
      <h2 id="ai-providers">{t("ai.providers.title")}</h2>
      <ul className={styles.list}>
        {(providers.data ?? []).map((provider) => (
          <li key={provider.id} className={styles.card}>
            <strong>{provider.name}</strong>{" "}
            <span className={styles.meta}>
              {catalogue.kinds.find((k) => k.name === provider.kind)?.label ?? provider.kind} · {provider.endpoint} ·{" "}
              {provider.key_hint === null ? t("ai.providers.noKey") : t("ai.providers.key", { hint: provider.key_hint })}
            </span>{" "}
            <button
              type="button"
              className={styles.button}
              onClick={() => {
                remove.mutate(provider.id);
              }}
            >
              {t("ai.providers.remove", { name: provider.name })}
            </button>
            <ContextWindow
              provider={provider}
              local={catalogue.kinds.find((k) => k.name === provider.kind)?.custom_models === true}
            />
          </li>
        ))}
        {providers.data?.length === 0 && <li className={styles.meta}>{t("ai.providers.empty")}</li>}
      </ul>
      <form
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault();
          add.mutate(
            { name, kind, endpoint, api_key: key === "" ? null : key },
            {
              onSuccess: () => {
                setName("");
                setKey("");
              },
            },
          );
        }}
      >
        <h3>{t("ai.providers.add")}</h3>
        <div className={styles.field}>
          <label htmlFor="ai-kind">{t("ai.providers.kind")}</label>
          <select
            id="ai-kind"
            value={kind}
            onChange={(event) => {
              const next = catalogue.kinds.find((k) => k.name === event.target.value);
              setKind(event.target.value);
              setEndpoint(next?.endpoint ?? "");
            }}
          >
            {catalogue.kinds.map((k) => (
              <option key={k.name} value={k.name}>
                {k.label}
              </option>
            ))}
          </select>
        </div>
        <div className={styles.field}>
          <label htmlFor="ai-name">{t("ai.providers.name")}</label>
          <input
            id="ai-name"
            required
            maxLength={80}
            value={name}
            onChange={(event) => {
              setName(event.target.value);
            }}
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="ai-endpoint">{t("ai.providers.endpoint")}</label>
          <input
            id="ai-endpoint"
            required
            value={endpoint}
            onChange={(event) => {
              setEndpoint(event.target.value);
            }}
          />
          {chosen?.custom_models === true && <span className={styles.help}>{t("ai.providers.localHelp")}</span>}
        </div>
        {chosen?.api_key === true && (
          <div className={styles.field}>
            <label htmlFor="ai-key">{t("ai.providers.apiKey")}</label>
            <input
              id="ai-key"
              type="password"
              autoComplete="off"
              required
              value={key}
              onChange={(event) => {
                setKey(event.target.value);
              }}
            />
            <span className={styles.help}>{t("ai.providers.keyHelp")}</span>
          </div>
        )}
        {add.error !== null && (
          <p role="alert" className={styles.error}>
            {errorOf(t, add.error)}
          </p>
        )}
        <p>
          <button type="submit" className={styles.primary} disabled={add.isPending}>
            {t("ai.providers.save")}
          </button>
        </p>
      </form>
    </section>
  );
}

interface Row {
  providerId: string;
  model: string;
}

function Profile({ catalogue }: { catalogue: CatalogueView }) {
  const { t } = useTranslation();
  const providers = useQuery(providersQuery);
  const profile = useQuery(profileQuery);
  const save = useSaveProfile();
  const [rows, setRows] = useState<Row[] | null>(null);
  const shown: Row[] =
    rows ?? (profile.data?.entries ?? []).map((e) => ({ providerId: e.provider_id, model: e.model }));
  const list = providers.data ?? [];
  const update = (next: Row[]) => {
    setRows(next);
  };
  const modelsOf = (provider: ProviderView | undefined) =>
    provider === undefined ? [] : catalogue.models.filter((m) => m.provider === provider.kind);
  return (
    <section className={styles.panel} aria-labelledby="ai-profile">
      <h2 id="ai-profile">{t("ai.profile.title")}</h2>
      <p className={styles.help}>{t("ai.profile.help")}</p>
      <p className={styles.help}>{t("ai.profile.statuses")}</p>
      {list.length === 0 ? (
        <p className={styles.meta}>{t("ai.profile.noProvider")}</p>
      ) : (
        <ol className={styles.list}>
          {shown.map((row, index) => {
            const provider = list.find((p) => p.id === row.providerId);
            const models = modelsOf(provider);
            const kind = catalogue.kinds.find((k) => k.name === provider?.kind);
            const status = models.find((m) => m.model === row.model)?.status ?? (kind?.custom_models ? "untested" : null);
            return (
              <li key={index} className={styles.row}>
                <select
                  aria-label={t("ai.profile.provider", { position: index + 1 })}
                  value={row.providerId}
                  onChange={(event) => {
                    const next = [...shown];
                    const chosen = list.find((p) => p.id === event.target.value);
                    next[index] = { providerId: event.target.value, model: modelsOf(chosen)[0]?.model ?? "" };
                    update(next);
                  }}
                >
                  {list.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
                {provider !== undefined && kind?.custom_models === true ? (
                  <LocalModel
                    providerId={provider.id}
                    position={index + 1}
                    value={row.model}
                    onChange={(model) => {
                      const next = [...shown];
                      next[index] = { ...row, model };
                      update(next);
                    }}
                  />
                ) : (
                  <>
                    <input
                      aria-label={t("ai.profile.model", { position: index + 1 })}
                      list={`ai-models-${String(index)}`}
                      value={row.model}
                      onChange={(event) => {
                        const next = [...shown];
                        next[index] = { ...row, model: event.target.value };
                        update(next);
                      }}
                    />
                    <datalist id={`ai-models-${String(index)}`}>
                      {models.map((m) => (
                        <option key={m.model} value={m.model} />
                      ))}
                    </datalist>
                  </>
                )}
                {status !== null && (
                  <span className={status === "tested" ? styles.good : status === "blocked" ? styles.danger : styles.limited}>
                    {t(`ai.status.${status}`)}
                  </span>
                )}
                <button
                  type="button"
                  className={styles.button}
                  disabled={index === 0}
                  aria-label={t("ai.profile.up", { position: index + 1 })}
                  onClick={() => {
                    const next = [...shown];
                    [next[index - 1], next[index]] = [next[index], next[index - 1]] as [Row, Row];
                    update(next);
                  }}
                >
                  ↑
                </button>
                <button
                  type="button"
                  className={styles.button}
                  aria-label={t("ai.profile.remove", { position: index + 1 })}
                  onClick={() => {
                    update(shown.filter((_, i) => i !== index));
                  }}
                >
                  ×
                </button>
              </li>
            );
          })}
        </ol>
      )}
      {list.length > 0 && (
        <p className={styles.row}>
          <button
            type="button"
            className={styles.button}
            onClick={() => {
              const first = list[0];
              if (first !== undefined) {
                update([...shown, { providerId: first.id, model: modelsOf(first)[0]?.model ?? "" }]);
              }
            }}
          >
            {t("ai.profile.add")}
          </button>
          <button
            type="button"
            className={styles.primary}
            disabled={save.isPending}
            onClick={() => {
              save.mutate(
                { entries: shown.map((r) => ({ provider_id: r.providerId, model: r.model })) },
                {
                  onSuccess: () => {
                    setRows(null);
                  },
                },
              );
            }}
          >
            {t("ai.profile.save")}
          </button>
          {save.isSuccess && rows === null && <span className={styles.meta}>{t("ai.saved")}</span>}
        </p>
      )}
      {save.error !== null && (
        <p role="alert" className={styles.error}>
          {errorOf(t, save.error)}
        </p>
      )}
    </section>
  );
}

const INSTALL = "__install__";

function size(bytes: number): string {
  return bytes >= 1e9 ? `${(bytes / 1e9).toFixed(1)} Go` : `${String(Math.round(bytes / 1e6))} Mo`;
}

/** The model of a local engine (Ollama): chosen among the models it has installed, or installed
 * from here when the administrator allows it (F05b). */
function LocalModel({
  providerId,
  position,
  value,
  onChange,
}: {
  providerId: string;
  position: number;
  value: string;
  onChange: (model: string) => void;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const installed = useQuery(installedQuery(providerId));
  const start = useStartPull();
  const [installing, setInstalling] = useState(false);
  const [wanted, setWanted] = useState("");
  const [pullId, setPullId] = useState<string | null>(null);
  const pull = useQuery({ ...pullQuery(pullId ?? ""), enabled: pullId !== null });
  const label = t("ai.profile.model", { position });
  if (installed.isError) {
    // The engine does not answer: the name is typed, as for any provider.
    return (
      <span className={styles.row}>
        <input
          aria-label={label}
          value={value}
          onChange={(event) => {
            onChange(event.target.value);
          }}
        />
        <span className={styles.warning}>{t("ai.models.unreachable")}</span>
      </span>
    );
  }
  if (installed.data === undefined) {
    return <span className={styles.meta}>{t("ai.models.loading")}</span>;
  }
  const names = installed.data.models.map((m) => m.name);
  const current = pull.data;
  const finished = current?.finished_at != null;
  const percent =
    current !== undefined && current.total > 0 ? Math.floor((100 * current.completed) / current.total) : null;
  return (
    <span className={styles.row}>
      <select
        aria-label={label}
        value={installing ? INSTALL : value}
        onChange={(event) => {
          if (event.target.value === INSTALL) {
            setInstalling(true);
          } else {
            setInstalling(false);
            onChange(event.target.value);
          }
        }}
      >
        {value !== "" && !names.includes(value) && (
          <option value={value}>{t("ai.models.notInstalled", { name: value })}</option>
        )}
        {value === "" && <option value="">{t("ai.models.choose")}</option>}
        {installed.data.models.map((m) => (
          <option key={m.name} value={m.name}>
            {m.name} ({size(m.size)})
          </option>
        ))}
        <option value={INSTALL}>{t("ai.models.install")}</option>
      </select>
      {installing &&
        (installed.data.can_install ? (
          <>
            <input
              aria-label={t("ai.models.name")}
              placeholder="qwen3:8b"
              maxLength={100}
              value={wanted}
              onChange={(event) => {
                setWanted(event.target.value);
              }}
            />
            <button
              type="button"
              className={styles.button}
              disabled={wanted.trim() === "" || start.isPending || (pullId !== null && !finished)}
              onClick={() => {
                start.mutate(
                  { providerId, model: wanted.trim() },
                  {
                    onSuccess: (created) => {
                      setPullId(created.id);
                    },
                  },
                );
              }}
            >
              {t("ai.models.start")}
            </button>
            <a href="https://ollama.com/library" target="_blank" rel="noreferrer">
              {t("ai.models.library")}
            </a>
          </>
        ) : (
          <span className={styles.notice}>{t("ai.models.notAllowed")}</span>
        ))}
      {start.error !== null && (
        <span role="alert" className={styles.error}>
          {errorOf(t, start.error)}
        </span>
      )}
      {current !== undefined && (
        <span role="status" className={current.status === "failed" ? styles.error : styles.meta}>
          {current.status === "running" &&
            (percent === null
              ? t("ai.models.preparing", { name: current.model })
              : t("ai.models.progress", {
                  name: current.model,
                  percent,
                  done: size(current.completed),
                  total: size(current.total),
                }))}
          {current.status === "done" && (
            <>
              {t("ai.models.done", { name: current.model })}{" "}
              <button
                type="button"
                className={styles.button}
                onClick={() => {
                  setInstalling(false);
                  setPullId(null);
                  setWanted("");
                  onChange(current.model);
                  void queryClient.invalidateQueries({ queryKey: installedQuery(providerId).queryKey });
                }}
              >
                {t("ai.models.use", { name: current.model })}
              </button>
            </>
          )}
          {current.status === "failed" && t("ai.models.failed", { name: current.model, error: current.error ?? "" })}
        </span>
      )}
    </span>
  );
}

/** The context window of a provider (decision of Joël, 2026-10-17): automatic, or the number of
 * tokens the user sets, which matters for a local engine whose window depends on its machine. */
function ContextWindow({ provider, local }: { provider: ProviderView; local: boolean }) {
  const { t } = useTranslation();
  const save = useSetContextWindow();
  const [custom, setCustom] = useState(provider.context_window !== null);
  const [value, setValue] = useState(String(provider.context_window ?? 16384));
  const name = `window-${provider.id}`;
  return (
    <fieldset className={styles.choices}>
      <legend>{t("ai.window.title")}</legend>
      <label>
        <input
          type="radio"
          name={name}
          checked={!custom}
          onChange={() => {
            setCustom(false);
          }}
        />{" "}
        {t("ai.window.auto")}
      </label>
      <label>
        <input
          type="radio"
          name={name}
          checked={custom}
          onChange={() => {
            setCustom(true);
          }}
        />{" "}
        {t("ai.window.custom")}
      </label>
      {custom && (
        <input
          type="number"
          aria-label={t("ai.window.tokens", { name: provider.name })}
          min={2048}
          max={2000000}
          step={1024}
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
          }}
        />
      )}
      <span className={styles.help}>{t(local ? "ai.window.helpLocal" : "ai.window.helpRemote")}</span>
      <p className={styles.row}>
        <button
          type="button"
          className={styles.button}
          disabled={save.isPending}
          onClick={() => {
            save.mutate({ id: provider.id, window: custom ? Number(value) : null });
          }}
        >
          {t("ai.window.save")}
        </button>
        {save.isSuccess && <span className={styles.meta}>{t("ai.saved")}</span>}
        {save.error !== null && (
          <span role="alert" className={styles.error}>
            {errorOf(t, save.error)}
          </span>
        )}
      </p>
    </fieldset>
  );
}

function Budget() {
  const { t } = useTranslation();
  const budget = useQuery(budgetQuery);
  const save = useSaveBudget();
  const [limit, setLimit] = useState<string | null>(null);
  if (budget.data === undefined) {
    return null;
  }
  const data = budget.data;
  return (
    <section className={styles.panel} aria-labelledby="ai-budget">
      <h2 id="ai-budget">{t("ai.budget.title")}</h2>
      <p className={styles.help}>{t("ai.budget.help")}</p>
      <p className={styles.meta}>
        {t("ai.budget.state", {
          spent: data.spent,
          reserved: data.reserved,
          usable: data.usable,
          currency: data.currency,
        })}
      </p>
      <form
        className={styles.row}
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate(limit ?? data.limit, {
            onSuccess: () => {
              setLimit(null);
            },
          });
        }}
      >
        <label htmlFor="ai-limit">{t("ai.budget.limit", { currency: data.currency })}</label>
        <input
          id="ai-limit"
          type="number"
          min="0"
          step="0.01"
          value={limit ?? data.limit}
          onChange={(event) => {
            setLimit(event.target.value);
          }}
        />
        <button type="submit" className={styles.primary} disabled={save.isPending}>
          {t("ai.budget.save")}
        </button>
      </form>
    </section>
  );
}

interface ModelResult {
  ok: boolean;
  error: string | null;
  provider: string | null;
  model: string | null;
  answer: { title?: string; keywords?: string[] } | null;
  repaired?: boolean;
  attempts: { provider: string; model: string; result: string; seconds: number }[];
}

/** What one model of the profile answered to « Tester ». */
function ModelOutcome({ model }: { model: ModelResult }) {
  const { t } = useTranslation();
  const seconds = model.attempts.reduce((total, a) => total + a.seconds, 0);
  const error = among(FAILURES, model.error ?? "") ? (model.error as (typeof FAILURES)[number]) : "unavailable";
  return (
    <div className={model.ok ? styles.success : styles.warning}>
      {model.ok ? (
        <>
          <p>{t("ai.check.ok", { provider: model.provider, model: model.model, seconds: seconds.toFixed(1) })}</p>
          <p>
            <strong>{model.answer?.title}</strong> — {(model.answer?.keywords ?? []).join(", ")}
          </p>
          {model.repaired === true && <p className={styles.meta}>{t("ai.check.repaired")}</p>}
        </>
      ) : (
        <p>
          {model.attempts[0] !== undefined && <strong>{model.attempts[0].model} : </strong>}
          {t(`ai.check.failed.${error}`)}
        </p>
      )}
      <ul className={styles.journal}>
        {model.attempts.map((a, i) => (
          <li key={i}>
            {a.provider} · {a.model} · {resultText(t, a.result)} · {a.seconds} s
          </li>
        ))}
      </ul>
    </div>
  );
}

function Check() {
  const { t } = useTranslation();
  const start = useStartCheck();
  const [checkId, setCheckId] = useState<string | null>(null);
  const check = useQuery({ ...checkQuery(checkId ?? ""), enabled: checkId !== null });
  const result = check.data?.result as (ModelResult & { models?: ModelResult[] }) | null | undefined;
  // Each model of the profile was tried alone; an older check holds the first model only.
  const models = result == null ? [] : (result.models ?? [result]);
  const answered = models.filter((model) => model.ok).length;
  return (
    <section className={styles.panel} aria-labelledby="ai-check">
      <h2 id="ai-check">{t("ai.check.title")}</h2>
      <p className={styles.help}>{t("ai.check.help")}</p>
      <p>
        <button
          type="button"
          className={styles.primary}
          disabled={start.isPending || (checkId !== null && check.data?.finished_at == null)}
          onClick={() => {
            start.mutate(undefined, {
              onSuccess: (created) => {
                setCheckId(created.id);
              },
            });
          }}
        >
          {t("ai.check.start")}
        </button>
      </p>
      {checkId !== null && check.data?.finished_at == null && (
        <p role="status" className={styles.meta}>
          {t("ai.check.running")}
        </p>
      )}
      {result != null && (
        <div role="status">
          {models.length > 1 && <p>{t("ai.check.summary", { answered, count: models.length })}</p>}
          {models.map((model, index) => (
            <ModelOutcome key={index} model={model} />
          ))}
        </div>
      )}
    </section>
  );
}

function Policy({ catalogue }: { catalogue: CatalogueView }) {
  const { t } = useTranslation();
  const policy = useQuery(policyQuery);
  const save = useSavePolicy();
  const paidProviders = [...new Set(catalogue.models.filter((m) => m.paid).map((m) => m.provider))];
  const [allowed, setAllowed] = useState<string[] | null>(null);
  const [networks, setNetworks] = useState<string | null>(null);
  const [ports, setPorts] = useState<string | null>(null);
  const [install, setInstall] = useState<boolean | null>(null);
  if (policy.data === undefined) {
    return null;
  }
  const data = policy.data;
  const currentAllowed = allowed ?? data.allowed_paid ?? [];
  return (
    <section className={styles.panel} aria-labelledby="ai-policy">
      <h2 id="ai-policy">{t("ai.policy.title")}</h2>
      <p className={styles.help}>{t("ai.policy.help")}</p>
      <form
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate(
            {
              allowed_paid: currentAllowed,
              local_networks: (networks ?? (data.local_networks ?? []).join("\n"))
                .split("\n")
                .map((n) => n.trim())
                .filter((n) => n !== ""),
              local_ports: (ports ?? (data.local_ports ?? []).join(", "))
                .split(/[\s,]+/)
                .filter((p) => p !== "")
                .map(Number),
              allow_model_install: install ?? data.allow_model_install,
            },
            {
              onSuccess: () => {
                setAllowed(null);
                setNetworks(null);
                setPorts(null);
                setInstall(null);
              },
            },
          );
        }}
      >
        <fieldset className={styles.choices}>
          <legend>{t("ai.policy.paid")}</legend>
          {paidProviders.map((provider) => (
            <label key={provider}>
              <input
                type="checkbox"
                checked={currentAllowed.includes(provider)}
                onChange={(event) => {
                  setAllowed(
                    event.target.checked
                      ? [...currentAllowed, provider]
                      : currentAllowed.filter((p) => p !== provider),
                  );
                }}
              />{" "}
              {catalogue.kinds.find((k) => k.name === provider)?.label ?? provider}
            </label>
          ))}
        </fieldset>
        <div className={styles.field}>
          <label htmlFor="ai-networks">{t("ai.policy.networks")}</label>
          <textarea
            id="ai-networks"
            rows={2}
            value={networks ?? (data.local_networks ?? []).join("\n")}
            onChange={(event) => {
              setNetworks(event.target.value);
            }}
          />
          <span className={styles.help}>{t("ai.policy.networksHelp")}</span>
        </div>
        <div className={styles.field}>
          <label htmlFor="ai-ports">{t("ai.policy.ports")}</label>
          <input
            id="ai-ports"
            value={ports ?? (data.local_ports ?? []).join(", ")}
            onChange={(event) => {
              setPorts(event.target.value);
            }}
          />
        </div>
        <label className={styles.check}>
          <input
            type="checkbox"
            checked={install ?? data.allow_model_install}
            onChange={(event) => {
              setInstall(event.target.checked);
            }}
          />{" "}
          {t("ai.policy.install")}
        </label>
        <span className={styles.help}>{t("ai.policy.installHelp")}</span>
        {save.error !== null && (
          <p role="alert" className={styles.error}>
            {errorOf(t, save.error)}
          </p>
        )}
        <p>
          <button type="submit" className={styles.primary} disabled={save.isPending}>
            {t("ai.policy.save")}
          </button>
          {save.isSuccess && <span className={styles.meta}> {t("ai.saved")}</span>}
        </p>
      </form>
    </section>
  );
}

function Journal() {
  const { t } = useTranslation();
  const calls = useQuery(callsQuery);
  const clear = useClearCalls();
  const [copied, setCopied] = useState(false);
  const [confirming, setConfirming] = useState(false);
  if (calls.data === undefined || calls.data.length === 0) {
    return null;
  }
  const text = calls.data
    .map(
      (call) =>
        `${formatDate(call.at)} · ${call.usage} · ${call.provider_kind} · ${call.model} · ${call.result}${call.detail ? ` (${call.detail})` : ""} · ${String(call.tokens_in)} → ${String(call.tokens_out)} jetons · ${call.seconds} s`,
    )
    .join("\n");
  return (
    <section className={styles.panel} aria-labelledby="ai-journal">
      <h2 id="ai-journal">{t("ai.journal.title")}</h2>
      <ul className={styles.journal}>
        {calls.data.slice(0, 20).map((call, index) => (
          <li key={index}>
            {formatDate(call.at)} · {call.provider_kind} · {call.model} · {resultText(t, call.result)} ·{" "}
            {t("ai.journal.tokens", { input: call.tokens_in, output: call.tokens_out })} · {call.seconds} s
          </li>
        ))}
      </ul>
      <p className={styles.row}>
        <button
          type="button"
          className={styles.button}
          onClick={() => {
            void navigator.clipboard.writeText(text).then(() => {
              setCopied(true);
            });
          }}
        >
          {t("ai.journal.copy")}
        </button>
        {copied && <span className={styles.meta}>{t("draft.details.copied")}</span>}
        {confirming ? (
          <>
            <span>{t("ai.journal.confirmClear")}</span>
            <button
              type="button"
              className={styles.button}
              onClick={() => {
                clear.mutate(undefined, {
                  onSuccess: () => {
                    setConfirming(false);
                  },
                });
              }}
            >
              {t("ai.journal.clear")}
            </button>
            <button
              type="button"
              className={styles.button}
              onClick={() => {
                setConfirming(false);
              }}
            >
              {t("brief.cancel")}
            </button>
          </>
        ) : (
          <button
            type="button"
            className={styles.button}
            onClick={() => {
              setConfirming(true);
            }}
          >
            {t("ai.journal.clear")}
          </button>
        )}
      </p>
    </section>
  );
}
