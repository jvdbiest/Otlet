// SPDX-License-Identifier: AGPL-3.0-or-later
// An agreement or a licence covering a whole source (Joël, 2026-10-20): the articles collected
// from the declaration on are read under it, within robots.txt and the limits of the site.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  sourceRightsQuery,
  useDeclareSourceRights,
  useWithdrawSourceRights,
  type SourceRightsBasis,
} from "../../collection.ts";
import { errorText, formatDate } from "./labels.ts";
import { styles } from "./styles.ts";

const BASES: readonly SourceRightsBasis[] = ["publisher_agreement", "licence"];

export function SourceRights({ workspaceId, sourceId, reserved }: { workspaceId: string; sourceId: string; reserved: boolean }) {
  const { t } = useTranslation();
  const rights = useQuery(sourceRightsQuery(workspaceId, sourceId));
  const declare = useDeclareSourceRights(workspaceId, sourceId);
  const withdraw = useWithdrawSourceRights(workspaceId, sourceId);
  const [basis, setBasis] = useState<SourceRightsBasis | null>(null);
  const [reference, setReference] = useState("");
  const [endsOn, setEndsOn] = useState("");
  const [certified, setCertified] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const data = rights.data;
  if (data === undefined) {
    return null;
  }
  const declaration = data.declaration;
  if (declaration !== null) {
    const ended = declaration.ends_on !== null && declaration.ends_on < new Date().toISOString().slice(0, 10);
    return (
      <div className={styles.warning} role="note">
        <p>
          <strong>{ended ? t("sourceRights.ended") : t("sourceRights.inForce")}</strong>
        </p>
        <p>
          {t("sourceRights.declared", { date: formatDate(declaration.declared_at) })}{" "}
          {t(`rights.bases.${declaration.basis}`)}
          {declaration.reference && ` (${declaration.reference})`}
          {declaration.ends_on !== null && ` · ${t("sourceRights.until", { date: declaration.ends_on })}`}
        </p>
        <p className={styles.meta}>« {declaration.commitment} »</p>
        {confirming ? (
          <p className={styles.row}>
            <span>{t("sourceRights.withdrawConfirm")}</span>
            <button
              type="button"
              className={styles.danger}
              disabled={withdraw.isPending}
              onClick={() => {
                withdraw.mutate();
              }}
            >
              {t("rights.withdraw")}
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
          </p>
        ) : (
          <p>
            <button
              type="button"
              className={styles.button}
              onClick={() => {
                setConfirming(true);
              }}
            >
              {t("rights.withdraw")}
            </button>
          </p>
        )}
      </div>
    );
  }
  if (!data.allowed || !reserved) {
    return null;
  }
  const ready = basis !== null && certified;
  return (
    <details className={styles.panel}>
      <summary>{t("sourceRights.open")}</summary>
      <p className={styles.help}>{t("sourceRights.help")}</p>
      <form
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault();
          if (basis !== null) {
            declare.mutate({ basis, reference, ends_on: endsOn === "" ? null : endsOn, certified });
          }
        }}
      >
        <fieldset className={styles.choices}>
          <legend>{t("rights.basis")}</legend>
          {BASES.map((value) => (
            <label key={value}>
              <input
                type="radio"
                name={`source-rights-${sourceId}`}
                checked={basis === value}
                onChange={() => {
                  setBasis(value);
                }}
              />{" "}
              {t(`rights.bases.${value}`)}
            </label>
          ))}
        </fieldset>
        <div className={styles.field}>
          <label htmlFor={`source-rights-ref-${sourceId}`}>{t("rights.reference")}</label>
          <input
            id={`source-rights-ref-${sourceId}`}
            maxLength={500}
            placeholder={t("rights.referenceExample")}
            value={reference}
            onChange={(event) => {
              setReference(event.target.value);
            }}
          />
        </div>
        <div className={styles.field}>
          <label htmlFor={`source-rights-end-${sourceId}`}>{t("sourceRights.endsOn")}</label>
          <input
            id={`source-rights-end-${sourceId}`}
            type="date"
            value={endsOn}
            onChange={(event) => {
              setEndsOn(event.target.value);
            }}
          />
        </div>
        <label>
          <input
            type="checkbox"
            checked={certified}
            onChange={(event) => {
              setCertified(event.target.checked);
            }}
          />{" "}
          {data.commitment}
        </label>
        <p className={styles.notice}>{t("rights.responsibility")}</p>
        {declare.error !== null && (
          <p role="alert" className={styles.error}>
            {errorText(t, declare.error)}
          </p>
        )}
        <p>
          <button type="submit" className={styles.primary} disabled={!ready || declare.isPending}>
            {t("sourceRights.submit")}
          </button>
        </p>
      </form>
    </details>
  );
}
