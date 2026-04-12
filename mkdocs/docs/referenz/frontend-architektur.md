# Frontend-Architektur

Übersicht der React-Frontend-Struktur, Component-Hierarchie und Best Practices.

---

## Technologie-Stack

| Layer | Technologie | Zweck |
| :--- | :--- | :--- |
| **Framework** | React 18.3 | UI Library |
| **Build Tool** | Vite 6.3 | Fast bundling & HMR |
| **Language** | TypeScript 5 | Type-safe development |
| **Styling** | Tailwind CSS 4 | Utility-first CSS |
| **Components** | Radix UI + MUI | Accessible primitives |
| **Routing** | React Router 7 | Client-side routing |
| **State** | React Context + React Query | Local & server state |
| **Form Handling** | React Hook Form | Lightweight forms |
| **Icons** | Lucide React | Icon library |
| **Notifications** | Sonner | Toast notifications |

---

## Verzeichnisstruktur

```
src/app/
├── App.tsx                        # Root component & routing
├── components/
│   ├── ui/                        # Base UI components (Button, Dialog, Table, etc.)
│   │   ├── button.tsx
│   │   ├── dialog.tsx
│   │   ├── form.tsx
│   │   ├── input.tsx
│   │   ├── sidebar.tsx
│   │   ├── table.tsx
│   │   ├── card.tsx
│   │   └── ... (~40 UI components)
│   ├── case-detail/               # Case detail page (Sub-components)
│   │   ├── CaseDetailView.tsx     # Main container
│   │   ├── CaseOverviewTab.tsx    # Tab: Overview
│   │   ├── CaseDocumentsTab.tsx   # Tab: Documents
│   │   ├── CaseFindingsTab.tsx    # Tab: Findings
│   │   └── DocumentViewDialog.tsx # Document preview
│   ├── figma/                     # Design system components
│   │   ├── ImageWithFallback.tsx  # Image placeholder handling
│   │   └── ...
│   ├── App.tsx
│   ├── ErrorBoundary.tsx
│   ├── app-header-user.tsx        # Header user menu
│   ├── activity-timeline.tsx      # Activity log display
│   ├── cases-search-filter.tsx    # Cases list filter
│   ├── dashboard-stats.tsx        # Dashboard statistics
│   ├── dsb-report-view.tsx        # DSB report rendering
│   ├── document-upload-zone.tsx   # Drag-drop file upload
│   ├── new-playbook-dialog.tsx    # Playbook creation modal
│   └── annotated-documents-view.tsx  # Annotated doc display
│
├── lib/
│   ├── api.ts                     # API client (fetch wrapper)
│   ├── hooks.ts                   # Custom React hooks
│   ├── utils.ts                   # Utility functions
│   └── types.ts                   # TypeScript types/interfaces
│
├── styles/
│   ├── globals.css                # Global styles
│   ├── tailwind.css               # Tailwind base
│   └── components.css             # Component-specific styles
│
└── main.tsx                       # Entry point
```

---

## Component-Hierarchie

### Seiten-Layout
```
<App>
  <Router>
    <Routes>
      <Route path="/cases" element={<CasesPage />} />
      <Route path="/cases/:id" element={<CaseDetailPage />} />
      <Route path="/playbooks" element={<PlaybooksPage />} />
      <Route path="/admin" element={<AdminPage />} />
      <Route path="/profile" element={<ProfilePage />} />
    </Routes>
  </Router>
</App>
```

### Case-Detail-Seite
```
<CaseDetailView>
  ├── <PageHeader>                 # Title, status, actions
  ├── <Tabs>
  │   ├── "Übersicht"
  │   │   └── <CaseOverviewTab>   # Basic info, timeline
  │   ├── "Dokumente"
  │   │   └── <CaseDocumentsTab>  # Upload, document list
  │   ├── "Findings"
  │   │   └── <CaseFindingsTab>   # Findings table, filters
  │   ├── "VVT"
  │   │   └── <VVTView>           # Normalization table
  │   ├── "DSB-Report"
  │   │   └── <DSBReportView>     # Report rendering
  │   ├── "Annotierte Dokumente"
  │   │   └── <AnnotatedDocsView> # Download links
  │   └── "Aktivitäten"
  │       └── <ActivityTimeline>  # Activity log
  └── <DocumentViewDialog>        # Modal for document preview
```

### Dashboard
```
<DashboardPage>
  ├── <DashboardStats>            # KPI cards (cases, findings, etc.)
  ├── <CasesSearchFilter>         # Search + filter
  ├── <Table>                     # Cases list
  │   ├── <TableHeader>
  │   ├── <TableBody>
  │   └── <TablePagination>
  └── <Dialogs>
      ├── <NewCaseDialog>
      └── <DeleteConfirmDialog>
```

---

## State Management

### 1. Server State (React Query)
Für Daten vom Backend (Cases, Findings, Documents).

**Beispiel:**
```typescript
// src/app/lib/hooks.ts
export function useCases() {
  return useQuery({
    queryKey: ["cases"],
    queryFn: () => api.get("/api/v1/cases/"),
  });
}

// In einer Komponente
function CasesList() {
  const { data: cases, isLoading } = useCases();
  return cases?.map(c => <CaseRow key={c.id} case={c} />);
}
```

### 2. Client State (React Context)
Für lokal verwaltete Zustände (Themes, User-Profil).

**Beispiel:**
```typescript
// src/app/contexts/UserContext.tsx
const UserContext = createContext<UserContextType | null>(null);

export function UserProvider({ children }) {
  const [user, setUser] = useState<User | null>(null);
  
  return (
    <UserContext.Provider value={{ user, setUser }}>
      {children}
    </UserContext.Provider>
  );
}

export const useUser = () => useContext(UserContext);
```

### 3. Form State (React Hook Form)
Für Formulare (New Case, Document Upload, etc.).

**Beispiel:**
```typescript
function NewCaseDialog() {
  const form = useForm<CaseFormData>({
    resolver: zodResolver(caseSchema),
    defaultValues: { title: "", description: "" },
  });

  return (
    <form onSubmit={form.handleSubmit(onSubmit)}>
      <FormField
        control={form.control}
        name="title"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Titel</FormLabel>
            <FormControl>
              <Input {...field} />
            </FormControl>
          </FormItem>
        )}
      />
    </form>
  );
}
```

---

## API-Integration

### API Client (`src/app/lib/api.ts`)
```typescript
import axios from "axios";

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
});

// Auto-inject JWT token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const api = {
  get: (path: string, config?) => apiClient.get(path, config),
  post: (path: string, data?: any, config?) => apiClient.post(path, data, config),
  patch: (path: string, data?: any, config?) => apiClient.patch(path, data, config),
  delete: (path: string, config?) => apiClient.delete(path, config),
};
```

### API Hooks Muster
```typescript
// useCase.ts
export function useCase(caseId: string) {
  return useQuery({
    queryKey: ["case", caseId],
    queryFn: () => api.get(`/api/v1/cases/${caseId}`),
  });
}

export function useUpdateCase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CaseUpdate) =>
      api.patch(`/api/v1/cases/${data.id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cases"] });
    },
  });
}
```

---

## Styling mit Tailwind CSS

### Utility-First Approach
```typescript
function Button({ variant = "primary", ...props }) {
  const baseClasses = "px-4 py-2 rounded font-semibold";
  const variantClasses = {
    primary: "bg-blue-600 text-white hover:bg-blue-700",
    secondary: "bg-gray-200 text-gray-800 hover:bg-gray-300",
    destructive: "bg-red-600 text-white hover:bg-red-700",
  };

  return (
    <button className={`${baseClasses} ${variantClasses[variant]}`} {...props}>
      {props.children}
    </button>
  );
}
```

### CSS Modules vs. Inline
Prefer Tailwind inline utilities over external CSS files. Use `*.css` only for:
- Global styles
- Custom animations
- Complex media queries

---

## Komponenten-Entwicklung

### Neue Component erstellen

**Datei:** `src/app/components/my-component.tsx`
```typescript
import React from "react";
import { Button } from "./ui/button";

interface MyComponentProps {
  title: string;
  onAction?: () => void;
}

export function MyComponent({ title, onAction }: MyComponentProps) {
  return (
    <div className="flex items-center gap-4 p-4 border rounded">
      <h2 className="text-lg font-semibold">{title}</h2>
      <Button variant="primary" onClick={onAction}>
        Action
      </Button>
    </div>
  );
}

export default MyComponent;
```

### Best Practices
1. **TypeScript Types:** Definiere Props-Interface
2. **Naming:** PascalCase für Components, camelCase für Funktionen
3. **Exports:** Named exports für Komponenten, default export optional
4. **Accessibility:** Nutze semantisches HTML, ARIA-Attribute
5. **Memoization:** `React.memo()` für teure Komponenten

---

## Testing

### Unit Tests (Vitest)
```typescript
// src/app/components/__tests__/MyComponent.test.tsx
import { render, screen } from "@testing-library/react";
import { MyComponent } from "../MyComponent";

describe("MyComponent", () => {
  it("renders title", () => {
    render(<MyComponent title="Test" />);
    expect(screen.getByText("Test")).toBeInTheDocument();
  });

  it("calls onAction when button clicked", () => {
    const handleAction = vi.fn();
    render(<MyComponent title="Test" onAction={handleAction} />);
    screen.getByRole("button").click();
    expect(handleAction).toHaveBeenCalled();
  });
});
```

### Integration Tests
```typescript
// Test mit echten API-Calls
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

function renderWithQuery(component: React.ReactElement) {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      {component}
    </QueryClientProvider>
  );
}
```

---

## Performance-Optimierungen

### 1. Code Splitting
```typescript
const CaseDetail = React.lazy(() => import("./pages/CaseDetail"));

function App() {
  return (
    <Suspense fallback={<Loading />}>
      <CaseDetail />
    </Suspense>
  );
}
```

### 2. Memoization
```typescript
const CaseRow = React.memo(function CaseRow({ case: _case }) {
  return <tr>...</tr>;
}, (prev, next) => prev.case.id === next.case.id);
```

### 3. Query Caching
```typescript
useQuery({
  queryKey: ["cases"],
  queryFn: () => api.get("/api/v1/cases/"),
  staleTime: 5 * 60 * 1000,   // 5 Minuten
  gcTime: 10 * 60 * 1000,     // 10 Minuten
});
```

---

## Theme & Dunkelmodus

### Theme-Context
```typescript
// src/app/contexts/ThemeContext.tsx
type ThemeType = "light" | "dark" | "system";

const ThemeContext = createContext<{
  theme: ThemeType;
  setTheme: (theme: ThemeType) => void;
}>(null);

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState<ThemeType>("system");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", shouldBeDark());
  }, [theme]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}
```

---

## Debugging & DevTools

### React DevTools
```bash
# Chrome Extension installieren
# Inspect komponenten, Props debuggen
```

### Vite DevTools
```bash
# HMR (Hot Module Replacement) aktiv während Development
# npm run dev
```

### Network Debugging
```bash
# Browser DevTools → Network Tab
# API-Requests, Response-Codes, Payloads prüfen
```

---

## Typische Workflows

### Neuen Case anzeigen
1. User klickt auf Case in Liste
2. `useCase(caseId)` Hook fetched Case-Details
3. CaseDetailView rendert Tabs
4. Documents/Findings/VVT/DSB-Report werden per API geladen
5. Bei Änderungen: `useUpdateCase()` Mutation, dann Query-Invalidation

### Dokument hochladen
1. User zieht File in `DocumentUploadZone`
2. Form mit `document_type`, `case_id` wird erstellt
3. `useMutation` für `POST /api/v1/documents/bulk`
4. Success → Toast-Notification
5. Query-Invalidation → Document-List aktualisiert

### Playbook-Check ausführen
1. User klickt „Checks ausführen" auf Case-Detail
2. Modal für Playbook-Auswahl
3. `useMutation` für `POST /api/v1/cases/{id}/run-checks`
4. Polling: `useQuery` für `GET /api/v1/cases/{id}/run-checks/status`
5. Nach Completion: Findings-Liste aktualisiert

---

## Ressourcen

- [React Documentation](https://react.dev/)
- [React Query (TanStack Query)](https://tanstack.com/query)
- [Tailwind CSS](https://tailwindcss.com/)
- [Radix UI](https://www.radix-ui.com/)
- [Vite](https://vitejs.dev/)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
