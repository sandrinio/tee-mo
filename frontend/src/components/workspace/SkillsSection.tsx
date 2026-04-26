/**
 * SkillsSection.tsx — Read-only skill catalog (STORY-025-04).
 *
 * Extracted verbatim from the inline route function (STORY-023-01 original).
 * Re-skinned to divider-list per W01 §3 STORY-025-04.
 *
 * ADR-023: Skills are chat-only CRUD — NO Edit button, NO Delete button.
 * Per W01 §3: no hover-reveal, no row actions.
 *
 * Per row:
 *   - Sparkles lucide icon (20px slate-500)
 *   - Mono `/teemo {name}` chip (rose-500 bg-rose-50)
 *   - Caption `{summary}` (slate-500 12px)
 *
 * Renders inside ModuleSection (card + header provided by parent).
 * Does NOT render its own h2 or outer card border.
 */

import { Sparkles } from 'lucide-react';
import { useSkillsQuery } from '../../hooks/useSkills';
import type { Skill } from '../../lib/api';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface SkillsSectionProps {
  workspaceId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * SkillsSection — read-only divider list of workspace skills.
 *
 * States:
 *   - Loading  — skeleton rows while query is in-flight.
 *   - Empty    — helper text (skills are created via Slack).
 *   - Populated — divider list, no row actions (ADR-023).
 */
export function SkillsSection({ workspaceId }: SkillsSectionProps) {
  const { data: skills, isLoading } = useSkillsQuery(workspaceId);

  if (isLoading) {
    return (
      <div className="divide-y divide-slate-100" data-testid="skills-loading">
        {[1, 2].map((i) => (
          <div key={i} className="flex items-center gap-3 px-4 py-3 animate-pulse">
            <div className="h-5 w-5 rounded bg-slate-200 shrink-0" />
            <div className="flex-1 space-y-1">
              <div className="h-3 w-1/4 rounded bg-slate-200" />
              <div className="h-3 w-2/3 rounded bg-slate-100" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!skills || skills.length === 0) {
    return (
      <div className="px-4 py-8 text-center" data-testid="skills-empty">
        <p className="text-sm text-slate-400">
          No skills yet. Teach Tee-Mo new behaviors directly in Slack.
        </p>
      </div>
    );
  }

  return (
    <ul className="divide-y divide-slate-100" data-testid="skills-list">
      {skills.map((skill: Skill) => (
        <li
          key={skill.name}
          className="flex items-center gap-3 px-4 py-3"
          data-testid={`skill-row-${skill.name}`}
        >
          {/* Sparkles icon (lucide) */}
          <Sparkles className="h-5 w-5 text-slate-500 shrink-0" data-testid="skill-sparkles-icon" />

          <div className="flex-1 min-w-0">
            {/* Mono /teemo {name} chip */}
            <span
              className="font-mono text-xs bg-rose-50 text-rose-500 px-2 py-0.5 rounded"
              data-testid={`skill-chip-${skill.name}`}
            >
              /teemo {skill.name}
            </span>
            {/* Summary caption — slate-500 12px */}
            <p className="text-xs text-slate-500 mt-1 truncate" data-testid={`skill-summary-${skill.name}`}>
              {skill.summary}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}
