// SPDX-License-Identifier: AGPL-3.0-or-later
// Routes of the interface. Every page except /connexion requires a session: without one, the
// visitor is sent to /connexion and comes back to the page they asked for.
import type { QueryClient } from "@tanstack/react-query";
import {
  createRootRouteWithContext,
  createRoute,
  createRouter,
  Outlet,
  redirect,
} from "@tanstack/react-router";
import { AppLayout } from "./layout/AppLayout.tsx";
import { EmptyPage, type Section } from "./pages/EmptyPage.tsx";
import { LoginPage } from "./pages/LoginPage.tsx";
import { NotFoundPage } from "./pages/NotFoundPage.tsx";
import { ItemPage } from "./pages/watch/ItemPage.tsx";
import { ItemsPage } from "./pages/watch/ItemsPage.tsx";
import { ManualPage } from "./pages/watch/ManualPage.tsx";
import { SourcesPage } from "./pages/watch/SourcesPage.tsx";
import { WatchLayout } from "./pages/watch/WatchLayout.tsx";
import { sessionQuery } from "./session.ts";

interface RouterContext {
  queryClient: QueryClient;
}

const rootRoute = createRootRouteWithContext<RouterContext>()({
  component: Outlet,
  notFoundComponent: NotFoundPage,
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/connexion",
  validateSearch: (search: Record<string, unknown>): { redirect?: string } =>
    typeof search.redirect === "string" ? { redirect: search.redirect } : {},
  beforeLoad: async ({ context }) => {
    if ((await context.queryClient.query(sessionQuery)) !== null) {
      // eslint-disable-next-line @typescript-eslint/only-throw-error -- TanStack Router's API
      throw redirect({ to: "/veille" });
    }
  },
  component: function Login() {
    return <LoginPage redirect={loginRoute.useSearch().redirect} />;
  },
});

const appRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "app",
  beforeLoad: async ({ context, location }) => {
    const session = await context.queryClient.query(sessionQuery);
    if (session === null) {
      // eslint-disable-next-line @typescript-eslint/only-throw-error -- TanStack Router's API
      throw redirect({ to: "/connexion", search: { redirect: location.href } });
    }
    return { session };
  },
  component: function App() {
    return <AppLayout session={appRoute.useRouteContext().session} />;
  },
});

const indexRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/",
  beforeLoad: () => {
    // eslint-disable-next-line @typescript-eslint/only-throw-error -- TanStack Router's API
    throw redirect({ to: "/veille" });
  },
});

function sectionRoute<Path extends string>(path: Path, section: Section) {
  return createRoute({
    getParentRoute: () => appRoute,
    path,
    component: () => <EmptyPage section={section} />,
  });
}

// The watch section (U01): items, sources, manual entry, and one item.
const watchRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/veille",
  component: WatchLayout,
});

const itemsRoute = createRoute({ getParentRoute: () => watchRoute, path: "/", component: ItemsPage });
const sourcesRoute = createRoute({ getParentRoute: () => watchRoute, path: "sources", component: SourcesPage });
const manualRoute = createRoute({ getParentRoute: () => watchRoute, path: "saisie", component: ManualPage });
const itemRoute = createRoute({
  getParentRoute: () => watchRoute,
  path: "elements/$itemId",
  component: function Item() {
    return <ItemPage itemId={itemRoute.useParams().itemId} />;
  },
});

const routeTree = rootRoute.addChildren([
  loginRoute,
  appRoute.addChildren([
    indexRoute,
    watchRoute.addChildren([itemsRoute, sourcesRoute, manualRoute, itemRoute]),
    sectionRoute("/redaction", "writing"),
    sectionRoute("/bibliotheque", "library"),
    sectionRoute("/reglages", "settings"),
  ]),
]);

export function createAppRouter(queryClient: QueryClient) {
  return createRouter({ routeTree, context: { queryClient }, defaultPreload: "intent" });
}

declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof createAppRouter>;
  }
}
