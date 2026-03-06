# Sprint 9: Retroactive Specifications

> **Sprint goal:** Fix critical playbook bugs (strategy generation, prompt leaks, editor), improve UX (markdown rendering, animations, navigation), and restructure the playbook from ICP-centric to GTM Strategy.

> **Written retroactively** based on the implementation plan and actual code changes across 5 feature branches.

---

## Track 1: Strategy Generation & Chat Intelligence

---

### BL-212: Fix Strategy Generation + Animation

**Problem:** Strategy generation produces tiny, truncated content because of a 150-word system prompt limit and a 4096 max_tokens cap, and there is no live animation showing progress during document writing.

**Solution:** Removed the 150-word limit from the system prompt, increased max_tokens from 4096 to 8192, added continuation logic that nudges the AI to write sections after research, and emits `section_update` SSE events so the editor refreshes live as sections are written.

#### AC-1: No word limit in system prompt
**Given** the strategy chat system prompt is assembled for a user session
**When** the system prompt text is inspected
**Then** it does NOT contain "MAXIMUM 150 words" and instead instructs "Write comprehensive, well-structured content"

#### AC-2: Increased max_tokens default
**Given** the Anthropic client's `query_with_tools` method is called
**When** no explicit `max_tokens` argument is provided
**Then** the default max_tokens value is 8192 (not 4096)

#### AC-3: Continuation nudge after research
**Given** the AI has called `web_search` during an agentic turn but has NOT called `update_strategy_section` or `append_to_section`
**When** the turn ends with `stop_reason != "tool_use"` and `iteration < 3`
**Then** a nudge message ("You have completed your research. Now proceed to write the strategy sections...") is appended and the agentic loop continues instead of returning

#### AC-4: Section update SSE events
**Given** the AI calls `update_strategy_section` or `append_to_section` successfully during a chat turn
**When** the tool execution completes without error
**Then** a `section_update` SSE event is emitted with `section`, `content`, and `action` ("update" or "append") fields

#### AC-5: Frontend handles section_update events
**Given** the user is on the Playbook page and the AI is streaming a response
**When** a `section_update` SSE event arrives
**Then** the `strategy-document` React Query cache is invalidated, causing the StrategyEditor to refetch and display the updated content

#### AC-6: SSE hook dispatches section_update
**Given** the SSE stream includes an event with `type: "section_update"`
**When** the `dispatchEvent` function in `useSSE.ts` processes it
**Then** the `onSectionUpdate` callback is invoked with a typed `SectionUpdateEvent` object containing `section`, `content`, and `action` fields

---

### BL-110: Agent Proactive Research

**Problem:** The AI jumps straight to writing sections without first presenting research findings, so users cannot verify or guide the AI's understanding before it writes.

**Solution:** Added a "RESEARCH WORKFLOW" instruction block to the system prompt that instructs the AI to research first, present findings, then write sections.

#### AC-1: Research workflow in system prompt
**Given** the strategy chat system prompt is assembled
**When** the full prompt text is inspected
**Then** it contains a "RESEARCH WORKFLOW" section with three phases: RESEARCH PHASE, WRITING PHASE, and VALIDATION

#### AC-2: Research phase instructions
**Given** the system prompt's RESEARCH WORKFLOW block
**When** the RESEARCH PHASE instruction is read
**Then** it instructs the AI to "Use web_search to gather data about the company, market, competitors, and industry trends" and "Present a brief summary (3-5 bullet points) of key findings to the user"

#### AC-3: Hypothesis-first approach
**Given** the system prompt's RESEARCH WORKFLOW block
**When** the research instructions are read
**Then** they instruct the AI to "form hypotheses first: 'Based on {domain}, I expect to find...' then validate with web_search"

---

### BL-211: Token Cost Tracking

**Problem:** Token costs may not be accurately aggregated across all turns in the agentic loop, and the `done` SSE event does not surface external tool costs (e.g., Perplexity web_search calls).

**Solution:** Refactored the `done` event payload into a `_build_done_data` helper that includes an `external_tool_costs` array listing each web_search call with its provider. All three `done` event emission sites now use this shared helper.

#### AC-1: External tool costs in done event
**Given** the AI calls `web_search` one or more times during an agentic turn
**When** the `done` SSE event is emitted
**Then** the event data includes an `external_tool_costs` array where each entry has `tool_name: "web_search"` and `provider: "perplexity"`

#### AC-2: No external costs when no web_search
**Given** the AI completes a turn without calling `web_search`
**When** the `done` SSE event is emitted
**Then** the `external_tool_costs` array is empty

#### AC-3: Consistent done event structure
**Given** the agentic loop can exit at three different points (budget exceeded, no tool calls, max iterations)
**When** any of these exit paths emits a `done` event
**Then** all three use the same `_build_done_data` helper producing identical payload structure with `tool_calls`, `model`, `total_input_tokens`, `total_output_tokens`, `total_cost_usd`, and `external_tool_costs`

---

### BL-202: Chat Tracks Strategy Gaps

**Problem:** The chat agent does not know which strategy sections are empty or incomplete, so it cannot proactively guide the user to fill gaps.

**Solution:** Added a "STRATEGY COMPLETENESS STATUS" block to the system prompt that classifies each of the 9 strategy sections as EMPTY, NEEDS WORK (<20 words), PARTIAL (<80 words), or COMPLETE (>=80 words), and instructs the AI to prioritize helping with empty/sparse sections.

#### AC-1: Completeness status in system prompt
**Given** a strategy document exists with some content
**When** the system prompt is assembled for a chat message
**Then** it contains a "STRATEGY COMPLETENESS STATUS:" block listing each of the 9 strategy sections with their status

#### AC-2: Empty section detection
**Given** the strategy document content does not contain a `## Buyer Personas` heading
**When** the completeness analysis runs
**Then** the "Buyer Personas" entry is marked `[EMPTY -- not yet written]`

#### AC-3: Sparse section detection
**Given** a strategy section heading exists but the section body has fewer than 20 words
**When** the completeness analysis runs
**Then** that section is marked `[NEEDS WORK -- only N words]` where N is the word count

#### AC-4: Partial section detection
**Given** a strategy section heading exists and the section body has between 20 and 79 words
**When** the completeness analysis runs
**Then** that section is marked `[PARTIAL -- N words]`

#### AC-5: Complete section detection
**Given** a strategy section heading exists and the section body has 80 or more words
**When** the completeness analysis runs
**Then** that section is marked `[COMPLETE -- N words]`

#### AC-6: Proactive guidance instruction
**Given** the STRATEGY COMPLETENESS STATUS block is present
**When** the system prompt is read
**Then** it contains the instruction "Prioritize helping the user fill EMPTY and NEEDS WORK sections" and suggests proactively asking to draft them

---

### BL-203: Context-Aware Chat Placeholder

**Problem:** The chat input always shows a generic placeholder regardless of what the user needs to do next.

**Solution:** Added a `compute_chat_placeholder` function on the backend that returns a dynamic placeholder based on document completeness and page context. On the frontend, the PlaybookPage uses `chat_placeholder` from the document API response, and ChatPanel uses page-specific placeholders for non-playbook pages.

#### AC-1: Backend placeholder computation
**Given** a strategy document with no content
**When** `compute_chat_placeholder` is called
**Then** it returns "Tell me about your company and I'll help build your GTM strategy..."

#### AC-2: Section-based placeholder
**Given** a strategy document where "Ideal Customer Profile (ICP)" heading is missing
**When** `compute_chat_placeholder` is called
**Then** it returns "Let's work on your Ideal Customer Profile (ICP)..."

#### AC-3: All sections complete placeholder
**Given** a strategy document where all 9 sections have 20+ words
**When** `compute_chat_placeholder` is called
**Then** it returns "Ask me to refine any section or move to Contacts..."

#### AC-4: PlaybookPage uses backend placeholder
**Given** the user is on the Playbook page and the document query returns `chat_placeholder`
**When** the chat input renders
**Then** the placeholder text matches the `chat_placeholder` value from the API (falling back to phase placeholders if absent)

#### AC-5: ChatPanel page-specific placeholders
**Given** the user is on the Contacts page
**When** the global ChatPanel input renders
**Then** the placeholder text is "Ask about your contacts or targeting criteria..."

#### AC-6: Phase-specific fallback
**Given** the user is on the Messages page and `currentPage` is "messages"
**When** the ChatPanel placeholder is computed
**Then** it shows "Help me craft outreach messages..."

---

## Track 2: Onboarding Flow

---

### BL-208: Fix System Prompt Leak

**Problem:** When onboarding triggers strategy generation, the full crafted prompt (containing internal instructions) is saved as a user message and displayed in the chat history.

**Solution:** Backend detects onboarding trigger messages that start with "Generate a complete GTM strategy" and marks them with `extra: {"hidden": true}`. Frontend filters hidden messages and renders a condensed "Strategy generation started..." placeholder instead.

#### AC-1: Onboarding trigger marked hidden
**Given** a chat message is sent that starts with "Generate a complete GTM strategy"
**When** the message is saved to the database
**Then** the `extra` JSONB field contains `{"hidden": true}`

#### AC-2: Non-trigger messages are not hidden
**Given** a chat message is sent that does NOT start with "Generate a complete GTM strategy"
**When** the message is saved to the database
**Then** the `extra` field is `null` (not marked as hidden)

#### AC-3: Hidden messages show condensed placeholder
**Given** the chat history contains a message with `extra.hidden === true`
**When** the ChatMessages component renders
**Then** instead of displaying the full message content, it shows a user-aligned bubble with italic text "Strategy generation started..."

#### AC-4: Hidden message has user avatar
**Given** a hidden onboarding trigger message is rendered
**When** the MessageBubble component renders
**Then** it displays the user icon avatar alongside the condensed "Strategy generation started..." text

#### AC-5: Normal messages unaffected
**Given** the chat history contains a regular user message (no `extra.hidden` flag)
**When** the ChatMessages component renders
**Then** the full message content is displayed normally

---

### BL-207: Editable Domain in Onboarding

**Problem:** The domain badge in onboarding is read-only, so users cannot correct a wrong auto-detected domain before strategy generation.

**Solution:** Replaced the static domain badge with an editable text input pre-filled from the tenant's domain. The edited domain value is passed to the `onGenerate` callback.

#### AC-1: Domain input pre-filled
**Given** the user opens the onboarding flow and the tenant has a domain configured (e.g., "acme.com")
**When** the PlaybookOnboarding component renders
**Then** a text input labeled "Company domain" is shown with the value "acme.com"

#### AC-2: Domain is editable
**Given** the domain input field is visible in the onboarding form
**When** the user clears the field and types "newdomain.io"
**Then** the input value updates to "newdomain.io"

#### AC-3: Edited domain passed to generation
**Given** the user has edited the domain to "newdomain.io" and typed a GTM objective
**When** the user submits the onboarding form
**Then** the `onGenerate` callback is invoked with `domains: ["newdomain.io"]` (the edited value, not the original tenant domain)

#### AC-4: Domain input disabled during generation
**Given** strategy generation is in progress (`isGenerating` is true)
**When** the onboarding form renders
**Then** the domain input field is disabled (has `disabled` attribute and reduced opacity)

#### AC-5: Empty domain handled
**Given** the user clears the domain input field entirely
**When** the form is submitted
**Then** the `onGenerate` callback receives `domains: []` (empty array)

---

### BL-206: Auto-Research on Onboarding

**Problem:** Background research does not start until the chat conversation begins. No pre-fetching of domain data occurs at space creation time.

**Solution:** Added a `trigger_initial_research` function that runs background domain research in a daemon thread when a new tenant space is created with a domain. The tenant creation endpoint calls this automatically.

#### AC-1: Research triggers on tenant creation
**Given** a new tenant space is created via `POST /api/tenants` with a `domain` field
**When** the tenant is successfully committed to the database
**Then** `trigger_initial_research` is called with the tenant ID and domain

#### AC-2: Self-company record created
**Given** `trigger_initial_research` is called for a tenant with domain "example.com"
**When** the function executes
**Then** a Company record with `is_self=True`, `domain="example.com"`, and `name="Example"` is created (or updated if one exists)

#### AC-3: Strategy document linked
**Given** `trigger_initial_research` runs for a tenant
**When** the self-company is created/found
**Then** the tenant's StrategyDocument `enrichment_id` is set to the self-company's ID

#### AC-4: Research runs in background thread
**Given** `trigger_initial_research` is called
**When** the company and document are set up
**Then** a daemon thread named "initial-research-{company_id}" is started to run `_run_self_research`

#### AC-5: Invalid domain skipped
**Given** `trigger_initial_research` is called with an empty or unsafe domain
**When** the domain validation fails
**Then** the function logs and returns without creating any records or threads

#### AC-6: Failure does not block tenant creation
**Given** `trigger_initial_research` raises an exception
**When** the error is caught in the tenant creation endpoint
**Then** the exception is logged as a warning but tenant creation still succeeds

---

## Track 3: Strategy Editor & Rich Content

---

### BL-205: Complex Object Selection & Deletion

**Problem:** Tables and Mermaid diagrams in the TipTap editor cannot be selected as a whole block or deleted easily.

**Solution:** Added `BlockToolbar` component with a delete button that appears on hover, enabled `allowTableNodeSelection` on the Table extension, added a `BlockDelete` keyboard extension for Backspace/Delete on block nodes, and added CSS for selection outlines on tables and mermaid blocks.

#### AC-1: Table node selection enabled
**Given** the TipTap editor contains a table
**When** the user clicks on the table to select it
**Then** the entire table can be selected as a node (indicated by a 2px accent-colored outline)

#### AC-2: BlockToolbar appears on Mermaid hover
**Given** the strategy editor contains a Mermaid diagram block
**When** the user hovers over the diagram
**Then** a floating toolbar with a trash icon appears at the top-right corner of the block

#### AC-3: BlockToolbar deletes the block
**Given** the BlockToolbar is visible over a Mermaid diagram
**When** the user clicks the trash icon button
**Then** the entire Mermaid block is deleted from the editor via `deleteRange`

#### AC-4: Backspace deletes selected block nodes
**Given** the user has selected a table or code block (selection is non-empty and cursor is inside a table/codeBlock node)
**When** the user presses Backspace or Delete
**Then** the `BlockDelete` extension calls `deleteSelection()` and removes the block

#### AC-5: Table selection outline
**Given** a table is selected as a node (`ProseMirror-selectednode` class)
**When** the table renders
**Then** it has a 2px solid accent-colored outline with 2px offset and 4px border radius

#### AC-6: Mermaid selection outline
**Given** a Mermaid block has the `ProseMirror-selectednode` class
**When** it renders
**Then** it has a 2px solid accent-colored outline with 2px offset

---

### BL-124: Sticky Format Toolbar

**Problem:** The editor toolbar scrolls out of view when editing long documents, forcing users to scroll back up to access formatting options.

**Solution:** The Toolbar component already has `sticky top-0 z-10` CSS classes. The fix sets `overflow: visible` on the `.strategy-editor` wrapper to prevent the parent scroll container from creating a new stacking/clipping context that blocks `position: sticky`.

#### AC-1: Toolbar has sticky positioning
**Given** the strategy editor is rendered in editable mode
**When** the Toolbar component renders
**Then** it has CSS classes `sticky top-0 z-10` with a `bg-surface` background and bottom border

#### AC-2: Overflow visible on wrapper
**Given** the `.strategy-editor` CSS class
**When** its styles are inspected
**Then** `overflow` is set to `visible` (ensuring sticky positioning works within the PhasePanel scroll container)

#### AC-3: Toolbar stays visible on scroll
**Given** the strategy editor has a long document that requires scrolling
**When** the user scrolls down past the toolbar's natural position
**Then** the toolbar remains fixed at the top of the visible area

---

### BL-209: Markdown Rendering in Tool Cards

**Problem:** Tool call result cards display raw markdown text (links, headers, bold text, lists) as plain text instead of rendered HTML.

**Solution:** Added ReactMarkdown rendering in the `FormattedValue` component for strings that contain markdown syntax and are longer than 50 characters. Added comprehensive CSS styles for markdown within tool cards.

#### AC-1: Markdown detected and rendered
**Given** a tool call result contains a string value with markdown syntax (e.g., `**bold**`, `[link](url)`, `# header`)
**When** the string is longer than 50 characters
**Then** the `FormattedValue` component renders it using `ReactMarkdown` inside a `div.tool-card-markdown` wrapper

#### AC-2: Short plain text not processed
**Given** a tool call result contains a short string (50 characters or fewer)
**When** the FormattedValue component renders it
**Then** it displays as a plain `<p>` element, NOT processed by ReactMarkdown

#### AC-3: Links are clickable
**Given** markdown content inside a tool card contains `[text](url)` links
**When** rendered
**Then** the links display as clickable elements with `color: var(--color-accent-cyan)` and underline on hover

#### AC-4: Headers are styled
**Given** markdown content contains `#`, `##`, or `###` headings
**When** rendered inside a tool card
**Then** the headings render at `0.8rem` font size with `font-weight: 600`

#### AC-5: Lists display correctly
**Given** markdown content contains unordered or ordered lists
**When** rendered inside a tool card
**Then** unordered lists show disc markers and ordered lists show decimal numbers, both with `1.25rem` left padding

#### AC-6: Code blocks styled
**Given** markdown content contains inline code or fenced code blocks
**When** rendered
**Then** inline code has `bg-surface-alt` background with rounded corners, and code blocks have padding and horizontal scroll

---

### BL-123: Mermaid Diagram Rendering

**Problem:** Mermaid diagrams may not render consistently with the app's dark theme, and text colors may be hard to read.

**Solution:** Enhanced the mermaid initialization with additional dark-theme variables (node text color, edge label background, cluster colors, title color, font family) and added CSS overrides to ensure SVG text uses the design system's text color variables.

#### AC-1: Dark theme configuration
**Given** the mermaid library is initialized via `getMermaid()`
**When** the initialization config is inspected
**Then** it uses `theme: 'dark'` with `themeVariables` including `nodeTextColor: '#E8E0F0'`, `edgeLabelBackground: '#1A1E28'`, `clusterBkg: '#1A1E28'`, `titleColor: '#E8EAF0'`, and `fontFamily: '"Work Sans", system-ui, sans-serif'`

#### AC-2: SVG text color override
**Given** a Mermaid diagram renders as SVG inside `.strategy-editor`
**When** the diagram is displayed
**Then** CSS rule `.strategy-editor .mermaid-svg-container svg text` sets `fill` to `var(--color-text)` to ensure readability

#### AC-3: Edge label color
**Given** a Mermaid diagram with labeled edges renders
**When** the edge labels are displayed
**Then** CSS rule `.strategy-editor .mermaid-svg-container svg .edgeLabel` sets `color` to `var(--color-text-muted)`

---

## Track 4: Navigation & Naming

---

### BL-197: Rename ICP Playbook to GTM Strategy

**Problem:** The app still uses "ICP Playbook" naming throughout, but the product has evolved to a broader GTM Strategy tool.

**Solution:** Renamed all user-visible strings: "Playbook" pillar label to "GTM Strategy", "ICP Summary" sub-page to "Strategy Overview", page header from "ICP Playbook" to "GTM Strategy", "Extract ICP" button to "Analyze Market", and chat placeholder from "ICP strategy" to "GTM strategy".

#### AC-1: Pillar label renamed
**Given** the left navigation sidebar renders
**When** the user views the pillar icons
**Then** the playbook pillar label reads "GTM Strategy" (not "Playbook")

#### AC-2: Sub-page label renamed
**Given** the user clicks the GTM Strategy pillar in the sidebar
**When** the sub-page links render in the second tier
**Then** the link text reads "Strategy Overview" (not "ICP Summary")

#### AC-3: Page header renamed
**Given** the user navigates to the playbook page
**When** the page header renders
**Then** the `<h1>` text reads "GTM Strategy" (not "ICP Playbook")

#### AC-4: Action button renamed
**Given** the user is on the strategy phase of the playbook page
**When** the phase action button renders
**Then** the button text reads "Analyze Market" with pending state "Analyzing..." (not "Extract ICP"/"Extracting...")

#### AC-5: Chat placeholder updated
**Given** the user is on the playbook page in strategy phase
**When** the chat input renders with no dynamic placeholder override
**Then** the fallback placeholder reads "Ask about your GTM strategy..." (not "Ask about your ICP strategy...")

#### AC-6: Toast message updated
**Given** the user triggers the market analysis action
**When** extraction completes successfully
**Then** the success toast reads "Market analysis extracted successfully" (not "ICP criteria extracted successfully")

---

### BL-125: Consistent Top Navigation

**Problem:** The gear dropdown and user menu in the top navigation are not logically organized, with settings scattered across two separate dropdowns.

**Solution:** Removed the standalone gear icon dropdown entirely. Consolidated all menu items into the user avatar dropdown, organized into three labeled groups: Personal (Preferences, Sign Out), Namespace (Users & Roles, Credits & Usage -- admin only), and Super Admin (LLM Costs -- super_admin only).

#### AC-1: Gear icon removed
**Given** the top navigation bar renders
**When** the user is logged in as any role
**Then** there is no standalone gear icon button in the nav bar

#### AC-2: User menu has Personal section
**Given** the user clicks their avatar/name in the top navigation
**When** the dropdown opens
**Then** it contains a "Personal" section header with "Preferences" link and "Sign Out" button

#### AC-3: User menu has Namespace section for admins
**Given** the user is a namespace admin
**When** the user dropdown is open
**Then** it contains a "Namespace" section with "Users & Roles" and "Credits & Usage" links

#### AC-4: Namespace section hidden for non-admins
**Given** the user has the "viewer" role (not admin)
**When** the user dropdown is open
**Then** the "Namespace" section is NOT visible

#### AC-5: Super Admin section for super_admins
**Given** the user is a super_admin
**When** the user dropdown is open
**Then** it contains a "Super Admin" section (with cyan-tinted header) containing "LLM Costs" link

#### AC-6: Sign Out replaces Logout
**Given** the user dropdown is open
**When** the sign-out option is visible
**Then** the button text reads "Sign Out" (not "Logout")

#### AC-7: Credits link navigates correctly
**Given** the user is a namespace admin and the dropdown is open
**When** the user clicks "Credits & Usage"
**Then** the browser navigates to `/{namespace}/admin/tokens`

---

### BL-112: Credits Link in User Dropdown

**Problem:** Users cannot easily find the credits/usage page from the navigation.

**Solution:** Added a "Credits & Usage" link in the Namespace section of the user dropdown that navigates to `/{namespace}/admin/tokens`. This is visible to namespace admins and above.

#### AC-1: Credits link visible for admins
**Given** the user has the "admin" role and opens the user dropdown
**When** the Namespace section renders
**Then** a "Credits & Usage" link is visible

#### AC-2: Credits link hidden for viewers
**Given** the user has only the "viewer" role
**When** the user dropdown renders
**Then** no "Credits & Usage" link is present

#### AC-3: Credits link navigates to tokens page
**Given** the user is in namespace "acme" and clicks "Credits & Usage"
**When** the navigation executes
**Then** the browser navigates to `/acme/admin/tokens`

---

## Track 5: Playbook Restructuring

---

### BL-198: ICP Tiers Tab

**Problem:** ICP tier definitions are buried in the strategy document as freeform text. They need a structured, dedicated tab for easy editing and AI extraction.

**Solution:** Added `GET/PUT /api/playbook/strategy/tiers` endpoints storing tier data in `extracted_data.tiers`, a `set_icp_tiers` AI tool, an `IcpTiersTab` frontend component with editable tier cards, and tab navigation on the PlaybookPage.

#### AC-1: Tab navigation visible
**Given** the user is on the playbook page in strategy phase and onboarding is complete
**When** the page renders
**Then** three tabs appear below the header: "Strategy Document", "ICP Tiers", and "Buyer Personas"

#### AC-2: GET tiers returns empty array
**Given** no tiers have been defined for the tenant
**When** `GET /api/playbook/strategy/tiers` is called
**Then** it returns `200` with `{"tiers": []}`

#### AC-3: PUT tiers creates/replaces
**Given** the user sends `PUT /api/playbook/strategy/tiers` with a tiers array
**When** the request is processed
**Then** the tiers are stored in `extracted_data.tiers`, other extracted data is preserved, and the response contains `{"status": "ok", "tiers": [...]}`

#### AC-4: Tiers tab renders cards
**Given** tiers exist in the backend (e.g., "Enterprise SaaS" with priority 1)
**When** the user clicks the "ICP Tiers" tab
**Then** the `IcpTiersTab` component renders tier cards with editable name, description, priority, and criteria fields

#### AC-5: Add tier
**Given** the user is on the ICP Tiers tab
**When** the user clicks the "Add Tier" button
**Then** a new empty tier card appears with blank fields ready for editing

#### AC-6: Delete tier
**Given** a tier card is displayed
**When** the user clicks the delete (X) button on that card
**Then** the tier is removed from the list and changes auto-save

#### AC-7: Tier criteria fields
**Given** a tier card is expanded
**When** the user edits criteria
**Then** they can add/remove industries (tag input), set company size range (min/max inputs), set revenue range (min/max inputs), add geographies (tag input), add tech signals (tag input), and add qualifying signals (tag input)

#### AC-8: AI tool for tier extraction
**Given** the AI is in a strategy chat session
**When** the AI calls the `set_icp_tiers` tool with a tiers array
**Then** the tiers are stored in `extracted_data.tiers`, a version snapshot is created, and the response includes `success: true` and `tier_count`

#### AC-9: Input validation
**Given** a `PUT /api/playbook/strategy/tiers` request is sent
**When** the `tiers` field is not an array
**Then** the endpoint returns `400` with `{"error": "tiers must be an array"}`

#### AC-10: Auth required
**Given** a request to `GET` or `PUT /api/playbook/strategy/tiers` is sent without an Authorization header
**When** the middleware processes it
**Then** the endpoint returns `401`

---

### BL-199: Buyer Personas Tab

**Problem:** Buyer personas are scattered in the strategy document text. They need a dedicated, structured tab.

**Solution:** Added `GET/PUT /api/playbook/strategy/personas` endpoints storing persona data in `extracted_data.personas`, a `set_buyer_personas` AI tool, and a `BuyerPersonasTab` frontend component with persona cards containing name, role, seniority, pain points, goals, channels, messaging hooks, objections, and linked tiers.

#### AC-1: GET personas returns empty array
**Given** no personas have been defined for the tenant
**When** `GET /api/playbook/strategy/personas` is called
**Then** it returns `200` with `{"personas": []}`

#### AC-2: PUT personas creates/replaces
**Given** the user sends `PUT /api/playbook/strategy/personas` with a personas array
**When** the request is processed
**Then** the personas are stored in `extracted_data.personas`, other extracted data is preserved, and the response contains `{"status": "ok", "personas": [...]}`

#### AC-3: Persona cards render with avatar
**Given** personas exist (e.g., "VP Engineering")
**When** the user clicks the "Buyer Personas" tab
**Then** persona cards render with a circular avatar showing the first letter of the persona name (e.g., "V")

#### AC-4: Persona fields are editable
**Given** a persona card is displayed
**When** the user interacts with it
**Then** they can edit: name (text input), role (text input), seniority (text input), pain points (tag input), goals (tag input), messaging hooks (tag input), and objections (tag input)

#### AC-5: Channel checkboxes
**Given** a persona card's "Preferred Channels" section
**When** the user views the channel selection
**Then** checkboxes for LinkedIn, Email, Phone, Twitter/X, Events, and Referral are displayed as toggle pills

#### AC-6: Linked tiers multi-select
**Given** ICP tiers have been defined (e.g., "Enterprise SaaS", "Mid-Market")
**When** the user views the "Linked ICP Tiers" section of a persona card
**Then** the available tier names appear as selectable toggle pills

#### AC-7: No tiers message
**Given** no ICP tiers have been defined
**When** the "Linked ICP Tiers" section renders
**Then** it shows "No ICP tiers defined yet. Add tiers in the ICP Tiers tab first."

#### AC-8: Add persona
**Given** the user is on the Buyer Personas tab
**When** the user clicks the "Add Persona" button
**Then** a new empty persona card appears with blank fields

#### AC-9: Delete persona
**Given** a persona card is displayed
**When** the user clicks the delete (X) button
**Then** the persona is removed and changes auto-save

#### AC-10: AI tool for persona extraction
**Given** the AI is in a strategy chat session
**When** the AI calls the `set_buyer_personas` tool with a personas array
**Then** the personas are stored in `extracted_data.personas`, a version snapshot is created, and the response includes `success: true` and `persona_count`

#### AC-11: Input validation
**Given** a `PUT /api/playbook/strategy/personas` request is sent
**When** the `personas` field is not an array
**Then** the endpoint returns `400` with `{"error": "personas must be an array"}`

#### AC-12: Auth required
**Given** a request to `GET` or `PUT /api/playbook/strategy/personas` is sent without auth
**When** the middleware processes it
**Then** the endpoint returns `401`

---

### BL-201: Remove Extract ICP -- Continuous Auto-Extraction

**Problem:** The manual "Extract ICP" button is a user friction point. ICP extraction should happen automatically as the strategy document is updated by the AI.

**Solution:** Removed the "Extract ICP" button, the ExtractionSidePanel component, and the `useExtractStrategy` hook. Added continuous extraction via system prompt instructions that tell the AI to proactively call `set_icp_tiers` and `set_buyer_personas` when strategy content exists but structures are missing. Added `needs_tier_extraction` and `needs_persona_extraction` flags to the playbook update response.

#### AC-1: Extract ICP button removed
**Given** the user is on the playbook page in strategy phase
**When** the page renders
**Then** there is no "Extract ICP" or "Analyze Market" button in the top bar action area for the strategy phase

#### AC-2: Extraction side panel removed
**Given** the user interacts with the playbook page
**When** any action is performed
**Then** the ExtractionSidePanel component is never rendered (it has been completely removed)

#### AC-3: Continuous extraction system prompt
**Given** a strategy document has content but `extracted_data.tiers` is empty
**When** the system prompt is assembled for a chat message
**Then** the prompt contains a "CONTINUOUS EXTRACTION" section instructing the AI to call `set_icp_tiers` proactively without asking for user permission

#### AC-4: Both tiers and personas extraction prompted
**Given** a strategy document has content but both `tiers` and `personas` are empty in extracted_data
**When** the system prompt is assembled
**Then** the CONTINUOUS EXTRACTION section includes hints for both ICP tier definitions and buyer persona definitions

#### AC-5: No extraction prompt when structures exist
**Given** a strategy document has content AND `extracted_data.tiers` is populated AND `extracted_data.personas` is populated
**When** the system prompt is assembled
**Then** no "CONTINUOUS EXTRACTION" section is present

#### AC-6: Extraction flags in update response
**Given** the user saves the playbook document with content containing "ideal customer" or "ICP" terms
**When** the `PUT /api/playbook` response is returned
**Then** it includes `needs_tier_extraction: true` when tiers are empty and the content mentions ICP-related terms, and `needs_persona_extraction: true` when personas are empty and the content mentions persona-related terms

#### AC-7: Tab navigation replaces extraction
**Given** the user wants to see extracted ICP tiers or buyer personas
**When** they click the "ICP Tiers" or "Buyer Personas" tab
**Then** they see the structured data in dedicated tab views (BL-198, BL-199) instead of the old ExtractionSidePanel
