/**
 * HeadersEditor.tsx — Dumb controlled component for editing HTTP header key-value pairs.
 *
 * Renders a table of [ key ] [ value ] [ × ] rows plus a "+ Add header" button.
 * Zero validation logic — the parent component owns validation and submission.
 *
 * Contract (STORY-012-04 §3.2):
 *   - Controlled: parent provides `rows` + `onChange`; this component never
 *     mutates state directly.
 *   - Empty rows (key === '') are the parent's responsibility to filter before submit.
 *   - Value inputs use type="password" by default to mask auth tokens.
 *   - Reusable for any "list of HTTP headers" need in future stories.
 *
 * jsdom note (FLASHCARD 2026-04-12 #vitest #frontend): jsdom lacks
 * HTMLDialogElement.showModal(); this component uses no dialog elements.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface HeaderRow {
  key: string;
  value: string;
}

export interface HeadersEditorProps {
  /** Controlled rows — each row is a key-value pair. */
  rows: HeaderRow[];
  /** Called with the updated array whenever a row changes. */
  onChange: (next: HeaderRow[]) => void;
  /** Input type for the value column. Default 'password' to mask tokens. */
  valueInputType?: 'password' | 'text';
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * HeadersEditor — controlled key-value table for HTTP headers.
 *
 * @example
 * ```tsx
 * const [headers, setHeaders] = useState([{ key: 'Authorization', value: '' }]);
 * <HeadersEditor rows={headers} onChange={setHeaders} />
 * ```
 */
export function HeadersEditor({
  rows,
  onChange,
  valueInputType = 'password',
}: HeadersEditorProps) {
  function updateKey(index: number, newKey: string) {
    const next = rows.map((r, i) => (i === index ? { ...r, key: newKey } : r));
    onChange(next);
  }

  function updateValue(index: number, newValue: string) {
    const next = rows.map((r, i) => (i === index ? { ...r, value: newValue } : r));
    onChange(next);
  }

  function removeRow(index: number) {
    onChange(rows.filter((_, i) => i !== index));
  }

  function addRow() {
    onChange([...rows, { key: '', value: '' }]);
  }

  return (
    <div className="space-y-2">
      {rows.map((row, i) => (
        <div key={i} className="flex items-center gap-2">
          {/* Key input */}
          <input
            type="text"
            value={row.key}
            onChange={(e) => updateKey(i, e.target.value)}
            placeholder="Header name"
            aria-label={`Header key ${i + 1}`}
            data-testid={`header-key-${i}`}
            className="flex-1 min-w-0 text-xs rounded border border-slate-300 px-2 py-1 text-slate-700 font-mono"
          />

          {/* Value input — masked by default for auth tokens */}
          <input
            type={valueInputType}
            value={row.value}
            onChange={(e) => updateValue(i, e.target.value)}
            placeholder={valueInputType === 'password' ? 'Bearer your-token' : 'value'}
            aria-label={`Header value ${i + 1}`}
            data-testid={`header-value-${i}`}
            className="flex-1 min-w-0 text-xs rounded border border-slate-300 px-2 py-1 text-slate-700 font-mono"
          />

          {/* Remove row button */}
          <button
            type="button"
            onClick={() => removeRow(i)}
            aria-label={`Remove header row ${i + 1}`}
            data-testid={`header-remove-${i}`}
            className="shrink-0 text-xs text-slate-400 hover:text-rose-500 px-1"
          >
            ×
          </button>
        </div>
      ))}

      {/* Add header button */}
      <button
        type="button"
        onClick={addRow}
        data-testid="header-add-row"
        className="text-xs font-semibold text-slate-500 hover:text-slate-800"
      >
        + Add header
      </button>

      {rows.length > 0 && (
        <p className="text-xs text-slate-400">
          Stored encrypted server-side, one value at a time. Each MCP server's README lists the
          required headers.
        </p>
      )}
    </div>
  );
}
