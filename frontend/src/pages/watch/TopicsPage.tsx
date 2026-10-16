// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { Button, Form, Input, Label, Text, TextArea, TextField } from "react-aria-components";
import { useTranslation } from "react-i18next";
import { sourcesQuery } from "../../collection.ts";
import { useWorkspaceId } from "../../session.ts";
import { topicsQuery, useDeleteTopic, useSaveTopic, type TopicView } from "../../watch.ts";
import { errorText, languageName, matchesFilter, TOPIC_LANGUAGES } from "./labels.ts";
import { RescoreStatus } from "./RescoreStatus.tsx";
import { emptyStyles, styles } from "./styles.ts";

/** The topics of the watch: their keywords, and how many items they gather (U02, F-VEI-01). */
export function TopicsPage() {
  const workspaceId = useWorkspaceId();
  return workspaceId === undefined ? null : <Topics workspaceId={workspaceId} />;
}

function Topics({ workspaceId }: { workspaceId: string }) {
  const { t } = useTranslation();
  const topics = useQuery(topicsQuery(workspaceId));
  // The topic being edited: null for a new one, undefined when the form is closed.
  const [editing, setEditing] = useState<TopicView | null | undefined>(undefined);

  return (
    <>
      <p>{t("topics.intro")}</p>
      {editing === undefined ? (
        <p>
          <Button
            className={styles.primary}
            onPress={() => {
              setEditing(null);
            }}
          >
            {t("topics.new")}
          </Button>
        </p>
      ) : (
        <TopicForm
          key={editing?.id ?? "new"}
          workspaceId={workspaceId}
          topic={editing}
          onDone={() => {
            setEditing(undefined);
          }}
        />
      )}
      {topics.isError && <p role="alert">{t("watch.loadFailed")}</p>}
      {topics.data?.length === 0 && (
        <div className={emptyStyles.empty}>
          <p className={emptyStyles.headline}>{t("topics.empty")}</p>
        </div>
      )}
      {topics.data !== undefined && topics.data.length > 0 && (
        <ul className={styles.list}>
          {topics.data.map((topic) => (
            <TopicCard
              key={topic.id}
              workspaceId={workspaceId}
              topic={topic}
              onEdit={() => {
                setEditing(topic);
              }}
            />
          ))}
        </ul>
      )}
    </>
  );
}

function TopicCard({ workspaceId, topic, onEdit }: { workspaceId: string; topic: TopicView; onEdit: () => void }) {
  const { t } = useTranslation();
  const remove = useDeleteTopic(workspaceId);
  const [confirming, setConfirming] = useState(false);
  const headingId = `topic-${topic.id}`;
  return (
    <li className={styles.card} aria-labelledby={headingId}>
      <h2 id={headingId}>
        <Link to="/veille/sujets/$topicId" params={{ topicId: topic.id }}>
          {topic.name}
        </Link>
      </h2>
      {topic.description !== "" && <p className={styles.meta}>{topic.description}</p>}
      <p className={styles.meta}>{t("topics.keywordsLabel", { terms: topic.keywords.join(", ") })}</p>
      {topic.exclusions.length > 0 && (
        <p className={styles.meta}>{t("topics.exclusionsLabel", { terms: topic.exclusions.join(", ") })}</p>
      )}
      <p className={styles.meta}>{t("topics.count", { count: topic.item_count })}</p>
      <RescoreStatus workspaceId={workspaceId} topic={topic} />
      <div className={styles.row}>
        <Button className={styles.button} onPress={onEdit}>
          {t("topics.modify")}
        </Button>
        {!confirming ? (
          <Button
            className={styles.danger}
            onPress={() => {
              setConfirming(true);
            }}
          >
            {t("topics.delete")}
          </Button>
        ) : (
          <span className={styles.row} role="group" aria-label={t("topics.confirmDelete")}>
            <span>{t("topics.confirmDelete")}</span>
            <Button
              className={styles.danger}
              autoFocus
              isDisabled={remove.isPending}
              onPress={() => {
                remove.mutate(topic.id);
              }}
            >
              {t("topics.confirm")}
            </Button>
            <Button
              className={styles.button}
              onPress={() => {
                setConfirming(false);
              }}
            >
              {t("topics.cancel")}
            </Button>
          </span>
        )}
      </div>
      {remove.error !== null && (
        <p role="alert" className={styles.error}>
          {errorText(t, remove.error)}
        </p>
      )}
    </li>
  );
}

// Keywords and exclusions per topic (otlet.watch.domain.model.TERMS_MAX).
const TERMS_MAX = 50;

/** How many terms are written, against the limit: the limit is visible before it is reached. */
function TermCount({ count }: { count: number }) {
  const { t } = useTranslation();
  const over = count > TERMS_MAX;
  return (
    <span aria-live="polite" className={over ? styles.error : styles.help}>
      {over
        ? t("topics.overLimit", { count, max: TERMS_MAX, excess: count - TERMS_MAX })
        : t("topics.counter", { count, max: TERMS_MAX })}
    </span>
  );
}

function lines(value: string): string[] {
  return value
    .split(/\n|,/)
    .map((line) => line.trim())
    .filter((line) => line !== "");
}

function TopicForm({
  workspaceId,
  topic,
  onDone,
}: {
  workspaceId: string;
  topic: TopicView | null;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const save = useSaveTopic(workspaceId);
  const sources = useQuery(sourcesQuery(workspaceId));
  const [name, setName] = useState(topic?.name ?? "");
  const [description, setDescription] = useState(topic?.description ?? "");
  const [keywords, setKeywords] = useState(topic?.keywords.join("\n") ?? "");
  const [exclusions, setExclusions] = useState(topic?.exclusions.join("\n") ?? "");
  const [languages, setLanguages] = useState<string[]>(topic?.languages ?? []);
  const [sourceIds, setSourceIds] = useState<string[]>(topic?.source_ids ?? []);
  const keywordCount = lines(keywords).length;
  const exclusionCount = lines(exclusions).length;
  const overLimit = keywordCount > TERMS_MAX || exclusionCount > TERMS_MAX;

  return (
    <section className={styles.panel} aria-labelledby="topic-form">
      <h2 id="topic-form">{topic === null ? t("topics.new") : t("topics.edit", { name: topic.name })}</h2>
      <Form
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate(
            {
              topicId: topic?.id ?? null,
              body: {
                name,
                description,
                keywords: lines(keywords),
                exclusions: lines(exclusions),
                languages,
                source_ids: sourceIds,
              },
            },
            { onSuccess: onDone },
          );
        }}
      >
        <TextField className={styles.field} value={name} onChange={setName} isRequired maxLength={200}>
          <Label>{t("topics.name")}</Label>
          <Input />
        </TextField>
        <TextField className={styles.field} value={description} onChange={setDescription} maxLength={2000}>
          <Label>{t("topics.description")}</Label>
          <Input />
        </TextField>
        <TextField className={styles.field} value={keywords} onChange={setKeywords} isRequired>
          <Label>{t("topics.keywords")}</Label>
          <TextArea rows={4} />
          <Text slot="description" className={styles.help}>
            {t("topics.keywordsHelp")}
          </Text>
          <TermCount count={keywordCount} />
        </TextField>
        <TextField className={styles.field} value={exclusions} onChange={setExclusions}>
          <Label>{t("topics.exclusions")}</Label>
          <TextArea rows={2} />
          <Text slot="description" className={styles.help}>
            {t("topics.exclusionsHelp")}
          </Text>
          <TermCount count={exclusionCount} />
        </TextField>
        <Choices
          legend={t("topics.languages")}
          options={TOPIC_LANGUAGES.map((code) => ({ value: code, label: languageName(t, code) }))}
          value={languages}
          onChange={setLanguages}
        />
        {sources.data !== undefined && sources.data.length > 0 && (
          <Choices
            legend={t("topics.sources")}
            options={sources.data.map((source) => ({ value: source.id, label: source.name }))}
            value={sourceIds}
            onChange={setSourceIds}
            filterLabel={t("topics.filterSources")}
          />
        )}
        {save.error !== null && (
          <p role="alert" className={styles.error}>
            {errorText(t, save.error)}
          </p>
        )}
        <div className={styles.row}>
          <Button type="submit" className={styles.primary} isDisabled={save.isPending || overLimit}>
            {t("topics.save")}
          </Button>
          <Button className={styles.button} onPress={onDone}>
            {t("topics.cancel")}
          </Button>
        </div>
      </Form>
    </section>
  );
}

/** Native checkboxes in a fieldset: none checked means "all". */
function Choices({
  legend,
  options,
  value,
  onChange,
  filterLabel,
}: {
  legend: string;
  options: { value: string; label: string }[];
  value: string[];
  onChange: (value: string[]) => void;
  filterLabel?: string;
}) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  // The filter only hides boxes: what is checked stays checked, and is counted.
  const shown = query.trim() === "" ? options : options.filter((o) => matchesFilter(o.label, query));
  const hiddenChecked = value.filter((v) => !shown.some((o) => o.value === v)).length;
  return (
    <fieldset className={styles.choices}>
      <legend>{legend}</legend>
      {filterLabel !== undefined && (
        <div className={styles.choicesTools}>
          <input
            type="search"
            aria-label={filterLabel}
            placeholder={filterLabel}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
            }}
          />
          {value.length > 0 && (
            <span aria-live="polite" className={styles.help}>
              {t("topics.checked", { count: value.length })}
              {hiddenChecked > 0 && <> {t("topics.hiddenChecked", { hidden: hiddenChecked })}</>}
            </span>
          )}
          {shown.length === 0 && (
            <span className={styles.help}>{t("topics.noSourceMatch", { q: query.trim() })}</span>
          )}
        </div>
      )}
      {shown.map((option) => (
        <label key={option.value}>
          <input
            type="checkbox"
            checked={value.includes(option.value)}
            onChange={(event) => {
              onChange(
                event.target.checked
                  ? [...value, option.value]
                  : value.filter((current) => current !== option.value),
              );
            }}
          />{" "}
          {option.label}
        </label>
      ))}
    </fieldset>
  );
}
