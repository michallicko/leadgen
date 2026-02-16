import { BrowserRouter, Routes, Route, Navigate } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './hooks/useAuth'
import { ToastProvider } from './components/ui/Toast'
import { AppShell } from './components/layout/AppShell'
import { LoginPage } from './components/layout/LoginPage'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { CompaniesPage } from './pages/companies/CompaniesPage'
import { ContactsPage } from './pages/contacts/ContactsPage'
import { MessagesPage } from './pages/messages/MessagesPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
        <BrowserRouter>
          <Routes>
            {/* Login — root page */}
            <Route path="/" element={<LoginPage />} />

            {/* Namespaced routes */}
            <Route path="/:namespace" element={<AppShell />}>
              <Route index element={<Navigate to="contacts" replace />} />
              <Route path="contacts" element={<ContactsPage />} />
              <Route path="companies" element={<CompaniesPage />} />
              <Route path="import" element={<PlaceholderPage title="Import Contacts" />} />
              <Route path="enrich" element={<PlaceholderPage title="Enrich Contacts" />} />
              <Route path="messages" element={<MessagesPage />} />
              <Route path="playbook" element={<PlaceholderPage title="ICP Summary" />} />
              <Route path="echo" element={<PlaceholderPage title="Dashboard Demo" />} />
            </Route>

            {/* Root-level admin pages (no namespace) */}
            <Route path="/admin" element={<AppShell />}>
              <Route index element={<PlaceholderPage title="Administration" />} />
            </Route>
            <Route path="/llm-costs" element={<AppShell />}>
              <Route index element={<PlaceholderPage title="LLM Cost Tracking" />} />
            </Route>
          </Routes>
        </BrowserRouter>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  )
}
