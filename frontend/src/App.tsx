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
import { MessageReviewPage } from './pages/messages/MessageReviewPage'
import { CampaignsPage } from './pages/campaigns/CampaignsPage'
import { CampaignDetailPage } from './pages/campaigns/CampaignDetailPage'
import { EnrichPage } from './pages/enrich/EnrichPage'
import { ImportPage } from './pages/import/ImportPage'
import { AdminPage } from './pages/admin/AdminPage'

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
              <Route path="import" element={<ImportPage />} />
              <Route path="enrich" element={<EnrichPage />} />
              <Route path="messages" element={<MessagesPage />} />
              <Route path="campaigns" element={<CampaignsPage />} />
              <Route path="campaigns/:campaignId" element={<CampaignDetailPage />} />
              <Route path="campaigns/:campaignId/review" element={<MessageReviewPage />} />
              <Route path="playbook" element={<PlaceholderPage title="ICP Playbook" description="Your Ideal Customer Profile definition — target segments, company signals, decision-maker titles, and disqualification criteria." />} />
              <Route path="echo" element={<PlaceholderPage title="Echo Analytics" description="Outreach performance dashboard — conversion funnels, response rates by channel, pipeline velocity." />} />
              <Route path="admin" element={<AdminPage />} />
              <Route path="llm-costs" element={<PlaceholderPage title="LLM Costs" description="AI usage tracking — cost over time, per-operation breakdown, per-tenant analysis, and call logs." />} />
            </Route>
          </Routes>
        </BrowserRouter>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  )
}
