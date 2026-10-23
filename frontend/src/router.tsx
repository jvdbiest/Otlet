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
import { ArticlePage } from "./pages/library/ArticlePage.tsx";
import { LibraryLayout } from "./pages/library/LibraryLayout.tsx";
import { LibraryPage } from "./pages/library/LibraryPage.tsx";
import { MediaPage } from "./pages/library/MediaPage.tsx";
import { LoginPage } from "./pages/LoginPage.tsx";
import { NotFoundPage } from "./pages/NotFoundPage.tsx";
import { ItemPage } from "./pages/watch/ItemPage.tsx";
import { ItemsPage } from "./pages/watch/ItemsPage.tsx";
import { ManualPage } from "./pages/watch/ManualPage.tsx";
import { SourcesPage } from "./pages/watch/SourcesPage.tsx";
import { TopicItemsPage } from "./pages/watch/TopicItemsPage.tsx";
import { TopicsPage } from "./pages/watch/TopicsPage.tsx";
import { WatchLayout } from "./pages/watch/WatchLayout.tsx";
import { AiSettingsPage } from "./pages/settings/AiSettingsPage.tsx";
import { BriefPage, BriefsPage, NewBriefPage } from "./pages/writing/BriefsPage.tsx";
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

// Writing (U03): the briefs, a new brief on items chosen in the watch, one brief.
const briefsRoute = createRoute({ getParentRoute: () => appRoute, path: "/redaction", component: BriefsPage });
const newBriefRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/redaction/nouveau",
  validateSearch: (search: Record<string, unknown>): { items: string } => ({
    items: typeof search.items === "string" ? search.items : "",
  }),
  component: function NewBrief() {
    return <NewBriefPage items={newBriefRoute.useSearch().items} />;
  },
});
const briefRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/redaction/briefs/$briefId",
  component: function Brief() {
    return <BriefPage briefId={briefRoute.useParams().briefId} />;
  },
});

// The Library (X04): the validated articles, and one article.
const libraryRoute = createRoute({ getParentRoute: () => appRoute, path: "/bibliotheque", component: LibraryLayout });
const articlesRoute = createRoute({
  getParentRoute: () => libraryRoute,
  path: "/",
  component: function Articles() {
    return <LibraryPage archived={false} />;
  },
});
const mediaRoute = createRoute({ getParentRoute: () => libraryRoute, path: "medias", component: MediaPage });
const archivesRoute = createRoute({
  getParentRoute: () => libraryRoute,
  path: "archives",
  component: function Archives() {
    return <LibraryPage archived />;
  },
});
const articleRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/bibliotheque/articles/$articleId",
  component: function Article() {
    return <ArticlePage articleId={articleRoute.useParams().articleId} />;
  },
});

// Settings (F05): the AI settings of the user.
const settingsRoute = createRoute({ getParentRoute: () => appRoute, path: "/reglages", component: AiSettingsPage });

// The watch section (U01): items, sources, manual entry, and one item.
const watchRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/veille",
  component: WatchLayout,
});

const itemsRoute = createRoute({ getParentRoute: () => watchRoute, path: "/", component: ItemsPage });
const sourcesRoute = createRoute({ getParentRoute: () => watchRoute, path: "sources", component: SourcesPage });
const topicsRoute = createRoute({ getParentRoute: () => watchRoute, path: "sujets", component: TopicsPage });
const topicRoute = createRoute({
  getParentRoute: () => watchRoute,
  path: "sujets/$topicId",
  component: function Topic() {
    return <TopicItemsPage topicId={topicRoute.useParams().topicId} />;
  },
});
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
    watchRoute.addChildren([itemsRoute, topicsRoute, topicRoute, sourcesRoute, manualRoute, itemRoute]),
    briefsRoute,
    newBriefRoute,
    briefRoute,
    libraryRoute.addChildren([articlesRoute, mediaRoute, archivesRoute]),
    articleRoute,
    settingsRoute,
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
