// SPDX-License-Identifier: AGPL-3.0-or-later
import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { Button, Form, Input, Label, Text, TextArea, TextField } from "react-aria-components";
import { useTranslation } from "react-i18next";
import { useAddManualText, useAddManualUrl, type ItemView } from "../../collection.ts";
import { useWorkspaceId } from "../../session.ts";
import { errorText } from "./labels.ts";
import { styles } from "./styles.ts";

/** Manual entry, framed (F-SRC-04, M-08): a page read under the rules of the sites, or a
 * pasted text whose origin and right of use the user declares. */
export function ManualPage() {
  const workspaceId = useWorkspaceId();
  const { t } = useTranslation();
  if (workspaceId === undefined) {
    return null;
  }
  return (
    <>
      <p>{t("manual.intro")}</p>
      <ManualUrl workspaceId={workspaceId} />
      <ManualText workspaceId={workspaceId} />
    </>
  );
}

function Added({ item }: { item: ItemView }) {
  const { t } = useTranslation();
  return (
    <p role="status" className={styles.success}>
      {t("manual.added")}{" "}
      <Link to="/veille/elements/$itemId" params={{ itemId: item.id }}>
        {t("manual.open")}
      </Link>
    </p>
  );
}

function ManualUrl({ workspaceId }: { workspaceId: string }) {
  const { t } = useTranslation();
  const add = useAddManualUrl(workspaceId);
  const [url, setUrl] = useState("");
  return (
    <section className={styles.panel} aria-labelledby="manual-url">
      <h2 id="manual-url">{t("manual.url.title")}</h2>
      <Form
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault();
          add.mutate(url, {
            onSuccess: () => {
              setUrl("");
            },
          });
        }}
      >
        <TextField className={styles.field} value={url} onChange={setUrl} isRequired inputMode="url">
          <Label>{t("manual.url.label")}</Label>
          <Input placeholder="https://" />
          <Text slot="description" className={styles.help}>
            {t("manual.url.help")}
          </Text>
        </TextField>
        {add.error !== null && (
          <p role="alert" className={styles.error}>
            {errorText(t, add.error)}
          </p>
        )}
        {add.data !== undefined && <Added item={add.data} />}
        <Button type="submit" className={styles.primary} isDisabled={add.isPending}>
          {t("manual.url.submit")}
        </Button>
      </Form>
    </section>
  );
}

const EMPTY = { title: "", text: "", url: "", declared_origin: "", usage_right: "" };

function ManualText({ workspaceId }: { workspaceId: string }) {
  const { t } = useTranslation();
  const add = useAddManualText(workspaceId);
  const [values, setValues] = useState(EMPTY);
  const field = (name: keyof typeof EMPTY) => ({
    value: values[name],
    onChange: (value: string) => {
      setValues((current) => ({ ...current, [name]: value }));
    },
  });

  return (
    <section className={styles.panel} aria-labelledby="manual-text">
      <h2 id="manual-text">{t("manual.text.title")}</h2>
      <p className={styles.warning} id="manual-warning">
        {t("manual.text.warning")}
      </p>
      <Form
        className={styles.form}
        aria-describedby="manual-warning"
        onSubmit={(event) => {
          event.preventDefault();
          const { url, ...rest } = values;
          add.mutate(url.trim() ? { ...rest, url: url.trim() } : rest, {
            onSuccess: () => {
              setValues(EMPTY);
            },
          });
        }}
      >
        <TextField className={styles.field} {...field("title")} isRequired maxLength={500}>
          <Label>{t("manual.text.titleLabel")}</Label>
          <Input />
        </TextField>
        <TextField className={styles.field} {...field("text")} isRequired>
          <Label>{t("manual.text.body")}</Label>
          <TextArea />
        </TextField>
        <TextField className={styles.field} {...field("url")} inputMode="url">
          <Label>{t("manual.text.url")}</Label>
          <Input placeholder="https://" />
        </TextField>
        <TextField className={styles.field} {...field("declared_origin")} isRequired maxLength={1000}>
          <Label>{t("manual.text.origin")}</Label>
          <Input />
          <Text slot="description" className={styles.help}>
            {t("manual.text.originHelp")}
          </Text>
        </TextField>
        <TextField className={styles.field} {...field("usage_right")} isRequired maxLength={1000}>
          <Label>{t("manual.text.right")}</Label>
          <Input />
          <Text slot="description" className={styles.help}>
            {t("manual.text.rightHelp")}
          </Text>
        </TextField>
        {add.error !== null && (
          <p role="alert" className={styles.error}>
            {errorText(t, add.error)}
          </p>
        )}
        {add.data !== undefined && <Added item={add.data} />}
        <Button type="submit" className={styles.primary} isDisabled={add.isPending}>
          {t("manual.text.submit")}
        </Button>
      </Form>
    </section>
  );
}
