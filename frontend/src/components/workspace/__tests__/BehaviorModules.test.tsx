/**
 * BehaviorModules.test.tsx — 5 Vitest scenarios for STORY-025-04.
 *
 * One test per Gherkin scenario:
 *   1. Persona behavior preserved — textarea edit + Save fires mutation with new bot_persona;
 *      "Saved successfully" pill appears on success.
 *   2. Skills divider list renders without Edit — 2 rows, Sparkles icon, mono chip,
 *      summary caption, NO edit button.
 *   3. Automation empty state matches handoff — zap tile, "No automations yet",
 *      caption, "Create automation" button.
 *   4. Automation populated state preserved — 2 automations render existing cards.
 *   5. Persona status reflects empty vs filled — resolver returns 'empty' for "",
 *      'ok' for non-empty; textarea renders with placeholder when empty.
 *
 * Strategy:
 *   - All hooks mocked via vi.mock; spy variables wrapped in vi.hoisted() (Vitest 2.x TDZ).
 *   - QueryClientProvider per test to prevent cache bleed-over.
 *   - No raw fetch() — all data through mocked hooks.
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ---------------------------------------------------------------------------
// Hoisted mock variables (FLASHCARD 2026-04-11 #vitest #test-harness)
// ---------------------------------------------------------------------------

const {
  mockUseUpdateWorkspaceMutation,
  mockUseSkillsQuery,
  mockUseAutomationsQuery,
  mockUseUpdateAutomationMutation,
  mockUseDeleteAutomationMutation,
} = vi.hoisted(() => ({
  mockUseUpdateWorkspaceMutation: vi.fn(),
  mockUseSkillsQuery: vi.fn(),
  mockUseAutomationsQuery: vi.fn(),
  mockUseUpdateAutomationMutation: vi.fn(),
  mockUseDeleteAutomationMutation: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

vi.mock('../../../hooks/useWorkspaces', () => ({
  useUpdateWorkspaceMutation: mockUseUpdateWorkspaceMutation,
}));

vi.mock('../../../hooks/useSkills', () => ({
  useSkillsQuery: mockUseSkillsQuery,
}));

vi.mock('../../../hooks/useAutomations', () => ({
  useAutomationsQuery: mockUseAutomationsQuery,
  useUpdateAutomationMutation: mockUseUpdateAutomationMutation,
  useDeleteAutomationMutation: mockUseDeleteAutomationMutation,
  // HOTFIX 2026-04-26: AutomationsSection now mounts AddAutomationModal +
  // DryRunModal + AutomationHistoryDrawer; their hooks must be stubbed.
  useCreateAutomationMutation: () => ({ mutate: vi.fn(), isPending: false, error: null }),
  useTestRunMutation: () => ({ mutate: vi.fn(), isPending: false, error: null, data: null, reset: vi.fn() }),
  useAutomationHistoryQuery: () => ({ data: [], isLoading: false, isError: false, error: null }),
  automationsKey: (wsId: string) => ['automations', wsId],
  automationHistoryKey: (wsId: string, aid: string) => ['automationHistory', wsId, aid],
}));

// HOTFIX 2026-04-26: stub the modals — BehaviorModules tests assert on
// AutomationsSection list/empty-state behavior, not on modal contents.
vi.mock('../AddAutomationModal', () => ({
  AddAutomationModal: ({ open }: { open: boolean }) =>
    open ? React.createElement('div', { 'data-testid': 'mock-add-automation-modal' }) : null,
}));
vi.mock('../DryRunModal', () => ({
  DryRunModal: ({ open }: { open: boolean }) =>
    open ? React.createElement('div', { 'data-testid': 'mock-dryrun-modal' }) : null,
}));
vi.mock('../AutomationHistoryDrawer', () => ({
  AutomationHistoryDrawer: ({ automationId }: { automationId: string | null }) =>
    automationId === null ? null : React.createElement('div', { 'data-testid': 'mock-history-drawer' }),
}));

// ---------------------------------------------------------------------------
// Import components after mocks are registered
// ---------------------------------------------------------------------------

import { PersonaSection } from '../PersonaSection';
import { SkillsSection } from '../SkillsSection';
import { AutomationsSection } from '../AutomationsSection';
import { MODULE_REGISTRY } from '../moduleRegistry';
import type { Automation } from '../../../types/automation';
import type { WorkspaceData } from '../types';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const WORKSPACE_ID = 'ws-behavior-test';

const MOCK_WORKSPACE = {
  id: WORKSPACE_ID,
  name: 'Test Workspace',
  bot_persona: 'Be helpful.',
  slack_team_id: 'T123',
  slack_team_name: null,
};

const SKILL_FIXTURE_1 = { name: 'daily-standup', summary: 'Summarize daily stand-up.' };
const SKILL_FIXTURE_2 = { name: 'onboarding', summary: 'Help new team members get started.' };

const AUTOMATION_FIXTURE_1: Automation = {
  id: 'auto-b-001',
  workspace_id: WORKSPACE_ID,
  owner_user_id: 'user-001',
  name: 'Weekly Digest',
  description: null,
  prompt: 'Summarize the week.',
  slack_channel_ids: [],
  schedule: { occurrence: 'weekly', when: '09:00', day_of_week: 'monday' },
  schedule_type: 'recurring',
  timezone: 'UTC',
  is_active: true,
  last_run_at: null,
  next_run_at: null,
  created_at: '2026-04-01T00:00:00Z',
  updated_at: '2026-04-01T00:00:00Z',
};

const AUTOMATION_FIXTURE_2: Automation = {
  ...AUTOMATION_FIXTURE_1,
  id: 'auto-b-002',
  name: 'Daily Briefing',
};

/** Default no-op mutation stubs. */
const stubMutation = {
  mutate: vi.fn(),
  mutateAsync: vi.fn(),
  isPending: false,
  isSuccess: false,
  isError: false,
  error: null,
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={makeClient()}>{children}</QueryClientProvider>;
}

// HOTFIX 2026-04-26: callback props removed — section is self-contained.
const defaultAutomationsProps = {
  workspaceId: WORKSPACE_ID,
  channelBindings: [],
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('BehaviorModules — STORY-025-04', () => {
  beforeEach(() => {
    mockUseUpdateAutomationMutation.mockReturnValue(stubMutation);
    mockUseDeleteAutomationMutation.mockReturnValue(stubMutation);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // =========================================================================
  // Scenario 1: Persona behavior preserved
  // =========================================================================

  it('Persona behavior preserved: textarea edit → Save fires mutation with new bot_persona; saved pill appears on success', async () => {
    const mockMutate = vi.fn();

    mockUseUpdateWorkspaceMutation.mockReturnValue({
      ...stubMutation,
      mutate: mockMutate,
      isSuccess: false,
    });

    render(
      <Wrapper>
        <PersonaSection workspace={MOCK_WORKSPACE} />
      </Wrapper>,
    );

    // Textarea is present
    const textarea = screen.getByRole('textbox');
    expect(textarea).toBeInTheDocument();

    // Change text to something different from the mock workspace value
    fireEvent.change(textarea, { target: { value: 'New persona text' } });

    // Click Save
    const saveButton = screen.getByRole('button', { name: /save persona/i });
    fireEvent.click(saveButton);

    // Mutation fires with new bot_persona
    expect(mockMutate).toHaveBeenCalledOnce();
    expect(mockMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        id: WORKSPACE_ID,
        bot_persona: 'New persona text',
      }),
    );

    // Rerender with isSuccess = true and hasChanged = false (value synced back)
    // Simulate success state: isSuccess=true, persona matches saved value
    mockUseUpdateWorkspaceMutation.mockReturnValue({
      ...stubMutation,
      mutate: mockMutate,
      isSuccess: true,
    });

    render(
      <Wrapper>
        <PersonaSection workspace={{ ...MOCK_WORKSPACE, bot_persona: 'New persona text' }} />
      </Wrapper>,
    );

    // Saved pill appears — hasChanged is false (current === saved)
    expect(screen.getByTestId('persona-saved-pill')).toBeInTheDocument();
    expect(screen.getByTestId('persona-saved-pill')).toHaveTextContent('Saved successfully');
  });

  // =========================================================================
  // Scenario 2: Skills divider list renders without Edit
  // =========================================================================

  it('Skills divider list renders without Edit: 2 rows, Sparkles icon, mono chip, summary, no Edit button', () => {
    mockUseSkillsQuery.mockReturnValue({
      data: [SKILL_FIXTURE_1, SKILL_FIXTURE_2],
      isLoading: false,
    });

    render(
      <Wrapper>
        <SkillsSection workspaceId={WORKSPACE_ID} />
      </Wrapper>,
    );

    // List is present
    const list = screen.getByTestId('skills-list');
    expect(list).toBeInTheDocument();

    // 2 rows separated by dividers (divide-y on the ul)
    const rows = list.querySelectorAll('li');
    expect(rows).toHaveLength(2);

    // Each row has the Sparkles icon (via data-testid)
    const sparklesIcons = screen.getAllByTestId('skill-sparkles-icon');
    expect(sparklesIcons).toHaveLength(2);

    // Mono /teemo chip for skill 1
    const chip1 = screen.getByTestId('skill-chip-daily-standup');
    expect(chip1).toHaveTextContent('/teemo daily-standup');
    expect(chip1.className).toMatch(/font-mono/);

    // Summary caption for skill 1
    expect(screen.getByTestId('skill-summary-daily-standup')).toHaveTextContent(
      'Summarize daily stand-up.',
    );

    // Mono /teemo chip for skill 2
    expect(screen.getByTestId('skill-chip-onboarding')).toHaveTextContent('/teemo onboarding');

    // Summary caption for skill 2
    expect(screen.getByTestId('skill-summary-onboarding')).toHaveTextContent(
      'Help new team members get started.',
    );

    // NO Edit button (ADR-023 chat-only CRUD)
    expect(screen.queryByRole('button', { name: /edit/i })).not.toBeInTheDocument();
  });

  // =========================================================================
  // Scenario 3: Automation empty state matches handoff
  // =========================================================================

  it('Automation empty state matches handoff: zap tile, headline, caption, Create automation button', () => {
    mockUseAutomationsQuery.mockReturnValue({
      data: [],
      isLoading: false,
    });

    render(
      <Wrapper>
        <AutomationsSection {...defaultAutomationsProps} />
      </Wrapper>,
    );

    // Empty state container
    const emptyState = screen.getByTestId('automations-empty-state');
    expect(emptyState).toBeInTheDocument();

    // Slate-100 zap-icon tile
    const zapTile = screen.getByTestId('automations-empty-zap-tile');
    expect(zapTile).toBeInTheDocument();
    expect(zapTile.className).toMatch(/bg-slate-100/);

    // "No automations yet" headline
    expect(emptyState).toHaveTextContent('No automations yet');

    // Caption text
    expect(emptyState).toHaveTextContent(
      'Trigger Tee-Mo on a schedule, on a Slack event, or from a webhook.',
    );

    // "Create automation" secondary button
    const createBtn = screen.getByTestId('create-automation-button');
    expect(createBtn).toBeInTheDocument();
    expect(createBtn).toHaveTextContent('Create automation');
  });

  // =========================================================================
  // Scenario 4: Automation populated state preserved
  // =========================================================================

  it('Automation populated state preserved: 2 automations render existing cards unchanged', () => {
    mockUseAutomationsQuery.mockReturnValue({
      data: [AUTOMATION_FIXTURE_1, AUTOMATION_FIXTURE_2],
      isLoading: false,
    });

    render(
      <Wrapper>
        <AutomationsSection {...defaultAutomationsProps} />
      </Wrapper>,
    );

    // No empty state visible
    expect(screen.queryByTestId('automations-empty-state')).not.toBeInTheDocument();

    // Both automation cards are present
    expect(screen.getByTestId('automation-card-auto-b-001')).toBeInTheDocument();
    expect(screen.getByTestId('automation-card-auto-b-002')).toBeInTheDocument();

    // Names render correctly
    expect(screen.getByTestId('automation-name-auto-b-001')).toHaveTextContent('Weekly Digest');
    expect(screen.getByTestId('automation-name-auto-b-002')).toHaveTextContent('Daily Briefing');

    // Action buttons present on first card
    expect(screen.getByTestId('history-button-auto-b-001')).toBeInTheDocument();
    expect(screen.getByTestId('toggle-button-auto-b-001')).toBeInTheDocument();
    expect(screen.getByTestId('delete-button-auto-b-001')).toBeInTheDocument();
  });

  // =========================================================================
  // Scenario 5: Persona status reflects empty vs filled
  // =========================================================================

  it('Persona status reflects empty vs filled: resolver returns empty for "", ok for non-empty; textarea renders with placeholder', () => {
    // Locate the persona registry entry
    const personaEntry = MODULE_REGISTRY.find((e) => e.id === 'persona');
    expect(personaEntry).toBeDefined();

    // Build minimal WorkspaceData shapes for the resolver
    const emptyData = {
      workspace: { ...MOCK_WORKSPACE, bot_persona: '' },
      drive: { connected: false },
      key: { has_key: false },
      channels: [],
      files: [],
      skills: [],
      automations: [],
    } as WorkspaceData;

    const filledData = {
      ...emptyData,
      workspace: { ...MOCK_WORKSPACE, bot_persona: 'Helpful internal assistant.' },
    };

    // Empty string → 'empty'
    expect(personaEntry!.statusResolver(emptyData)).toBe('empty');

    // Non-empty string → 'ok'
    expect(personaEntry!.statusResolver(filledData)).toBe('ok');

    // Render with empty bot_persona — textarea still renders with placeholder
    mockUseUpdateWorkspaceMutation.mockReturnValue(stubMutation);

    render(
      <Wrapper>
        <PersonaSection workspace={{ ...MOCK_WORKSPACE, bot_persona: '' }} />
      </Wrapper>,
    );

    const textarea = screen.getByRole('textbox');
    expect(textarea).toBeInTheDocument();
    expect(textarea).toHaveAttribute('placeholder');
    expect((textarea as HTMLTextAreaElement).placeholder).toBeTruthy();
  });
});
