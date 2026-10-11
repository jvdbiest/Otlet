// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, useState } from "react";

type HealthState = "checking" | "ok" | "unavailable";

const labels: Record<HealthState, string> = {
  checking: "Vérification du service…",
  ok: "Service disponible",
  unavailable: "Service indisponible",
};

export function App() {
  const [health, setHealth] = useState<HealthState>("checking");

  useEffect(() => {
    const controller = new AbortController();
    fetch("/health", { signal: controller.signal })
      .then((response) => {
        setHealth(response.ok ? "ok" : "unavailable");
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          console.error(error);
          setHealth("unavailable");
        }
      });
    return () => {
      controller.abort();
    };
  }, []);

  return (
    <main>
      <h1>Otlet</h1>
      <p>Version de démonstration, non destinée à la production.</p>
      <p role="status">{labels[health]}</p>
    </main>
  );
}
