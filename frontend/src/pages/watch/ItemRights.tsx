// SPDX-License-Identifier: AGPL-3.0-or-later
// A declaration of rights on a text its publisher reserves (Joël, 2026-10-20): one item at a
// time, a basis and a commitment the person accepts, a record kept; Otlet then reads the page
// under their responsibility, still within robots.txt and the limits of the site.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { rightsQuery, useDeclareRights, useWithdrawRights, type RightsBasis } from "../../collection.ts";
import { errorText, formatDate } from "./labels.ts";
import { styles } from "./styles.ts";

const BASES: readonly RightsBasis[] = ["publisher_agreement", "licence", "own_content", "other"];

export function ItemRights({ workspaceId, itemId, reason }: { workspaceId: string; itemId: string; reason: string | null }) {
  const { t } = useTranslation();
  const rights = useQuery(rightsQuery(workspaceId, itemId));
  const declare = useDeclareRights(workspaceId, itemId);
  const withdraw = useWithdrawRights(workspaceId, itemId);
  const [basis, setBasis] = useState<RightsBasis | null>(null);
  const [detail, setDetail] = useState("");
  const [reference, setReference] = useState("");
  const [certified, setCertified] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const data = rights.data;
  if (data === undefined) {
    return null;
  }
  const declaration = data.declaration;
  if (declaration !== null && reason === "declared_rights") {
    return (
      <div className={styles.warning} role="note">
        <p>
          <strong>{t("rights.importedTitle")}</strong>
        </p>
        <p>{t("rights.imported", { date: formatDate(declaration.declared_at) })}</p>
        <dl>
          <dt>{t("rights.basis")}</dt>
          <dd>
            {t(`rights.bases.${declaration.basis}`)}
            {declaration.detail && ` : ${declaration.detail}`}
          </dd>
          {declaration.reference && (
            <>
              <dt>{t("rights.reference")}</dt>
              <dd>{declaration.reference}</dd>
            </>
          )}
          <dt>{t("rights.commitmentKept")}</dt>
          <dd>« {declaration.commitment} »</dd>
        </dl>
        {confirming ? (
          <p className={styles.row}>
            <span>{t("rights.withdrawConfirm")}</span>
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
  if (!data.reserved || !data.allowed) {
    return null;
  }
  const ready = basis !== null && certified && (basis !== "other" || detail.trim() !== "");
  return (
    <details className={styles.panel}>
      <summary>{t("rights.open")}</summary>
      <p className={styles.help}>{t("rights.help")}</p>
      <form
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault();
          if (basis !== null) {
            declare.mutate({ basis, detail, reference, certified });
          }
        }}
      >
        <fieldset className={styles.choices}>
          <legend>{t("rights.basis")}</legend>
          {BASES.map((value) => (
            <label key={value}>
              <input
                type="radio"
                name="rights-basis"
                checked={basis === value}
                onChange={() => {
                  setBasis(value);
                }}
              />{" "}
              {t(`rights.bases.${value}`)}
            </label>
          ))}
        </fieldset>
        {basis === "other" && (
          <div className={styles.field}>
            <label htmlFor="rights-detail">{t("rights.detail")}</label>
            <input
              id="rights-detail"
              required
              maxLength={500}
              value={detail}
              onChange={(event) => {
                setDetail(event.target.value);
              }}
            />
          </div>
        )}
        <div className={styles.field}>
          <label htmlFor="rights-reference">{t("rights.reference")}</label>
          <input
            id="rights-reference"
            maxLength={500}
            placeholder={t("rights.referenceExample")}
            value={reference}
            onChange={(event) => {
              setReference(event.target.value);
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
            {t("rights.submit")}
          </button>
        </p>
      </form>
    </details>
  );
}
