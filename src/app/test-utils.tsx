import React from "react";
import { render, type RenderOptions } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, type MemoryRouterProps } from "react-router";

function makeTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

interface WrapperOptions {
  routerProps?: MemoryRouterProps;
  queryClient?: QueryClient;
}

function createWrapper({ routerProps, queryClient }: WrapperOptions = {}) {
  const client = queryClient ?? makeTestQueryClient();
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <MemoryRouter {...routerProps}>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  };
}

export function renderWithProviders(
  ui: React.ReactElement,
  options: RenderOptions & WrapperOptions = {},
) {
  const { routerProps, queryClient, ...renderOptions } = options;
  const wrapper = createWrapper({ routerProps, queryClient });
  return render(ui, { wrapper, ...renderOptions });
}

export { makeTestQueryClient };
export * from "@testing-library/react";
