// SPDX-License-Identifier: AGPL-3.0-or-later
import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { Button, Form, Input, Label, TextField } from "react-aria-components";
import { useTranslation } from "react-i18next";
import { ApiError } from "../api/client.ts";
import { useLogin } from "../session.ts";
import css from "./LoginPage.module.css";

const styles = css as Record<"page" | "card" | "intro" | "form" | "field" | "error" | "submit", string>;

export function LoginPage({ redirect }: { redirect: string | undefined }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const login = useLogin();
  const [values, setValues] = useState({ login: "", password: "" });

  function submit(event: { preventDefault(): void }) {
    event.preventDefault();
    login.mutate(values, {
      onSuccess: () => {
        // Only a path of this application: never an address given by someone else.
        const target = redirect?.startsWith("/") && !redirect.startsWith("//") ? redirect : "/veille";
        void navigate({ href: target });
      },
    });
  }

  return (
    <main className={styles.page}>
      <div className={styles.card}>
        <h1>{t("app.name")}</h1>
        <p className={styles.intro}>{t("login.intro")}</p>
        <Form onSubmit={submit} className={styles.form}>
          <TextField
            name="login"
            type="email"
            autoComplete="username"
            isRequired
            autoFocus
            value={values.login}
            onChange={(login) => {
              setValues((current) => ({ ...current, login }));
            }}
            className={styles.field}
          >
            <Label>{t("login.login")}</Label>
            <Input />
          </TextField>
          <TextField
            name="password"
            type="password"
            autoComplete="current-password"
            isRequired
            value={values.password}
            onChange={(password) => {
              setValues((current) => ({ ...current, password }));
            }}
            className={styles.field}
          >
            <Label>{t("login.password")}</Label>
            <Input />
          </TextField>
          {login.error !== null && (
            <p role="alert" className={styles.error}>
              {errorMessage(login.error, t)}
            </p>
          )}
          <Button type="submit" isDisabled={login.isPending} className={styles.submit}>
            {login.isPending ? t("login.submitting") : t("login.submit")}
          </Button>
        </Form>
      </div>
    </main>
  );
}

function errorMessage(error: Error, t: ReturnType<typeof useTranslation>["t"]): string {
  if (error instanceof ApiError && error.status === 401) {
    return t("login.invalidCredentials");
  }
  if (error instanceof ApiError && error.status === 429) {
    const minutes = Math.ceil((error.retryAfterSeconds ?? 900) / 60);
    return t("login.tooManyAttempts", { minutes });
  }
  return t("login.failed");
}
