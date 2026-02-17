import { BrowserRouter, Routes, Route, Navigate } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './hooks/useAuth'
import { ToastProvider } from './components/ui/Toast'
import { AppShell } from './components/layout/AppShell'
import { LoginPage } from './components/layout/LoginPage'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { CompaniesPage } from './pages/companies/CompaniesPage'
import { CompanyDetailPage } from './pages/companies/CompanyDetailPage'
import { ContactsPage } from './pages/contacts/ContactsPage'
import { ContactDetailPage } from './pages/contacts/ContactDetailPage'
import { MessagesPage } from './pages/messages/MessagesPage'
import { CampaignsPage } from './pages/campaigns/CampaignsPage'
import { CampaignDetailPage } from './pages/campaigns/CampaignDetailPage'
import { EnrichPage } from './pages/enrich/EnrichPage'

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
              <Route path="contacts/:contactId" element={<ContactDetailPage />} />
              <Route path="companies" element={<CompaniesPage />} />
              <Route path="companies/:companyId" element={<CompanyDetailPage />} />
              <Route path="import" element={<PlaceholderPage title="Import Contacts" />} />
              <Route path="enrich" element={<EnrichPage />} />
              <Route path="messages" element={<MessagesPage />} />
              <Route path="campaigns" element={<CampaignsPage />} />
              <Route path="campaigns/:campaignId" element={<CampaignDetailPage />} />
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
