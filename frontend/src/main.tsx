// SPDX-License-Identifier: AGPL-3.0-or-later
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./i18n.ts";
import { createAppRouter } from "./router.tsx";
import "./styles/global.css";

const container = document.getElementById("root");
if (container === null) {
  throw new Error("Missing #root element");
}

const queryClient = new QueryClient();
const router = createAppRouter(queryClient);

createRoot(container).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
