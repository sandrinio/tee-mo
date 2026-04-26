/**
 * HeadersEditor.test.tsx — unit tests for the controlled HeadersEditor component.
 *
 * Covers STORY-012-04 §4.1 HeadersEditor tests (3+):
 *   - Add row appends a new blank entry
 *   - Remove row deletes the correct row
 *   - onChange fires with the updated array on key/value input change
 */
import React, { useState } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { vi, describe, it, expect } from 'vitest';
import { HeadersEditor, type HeaderRow } from '../HeadersEditor';

// ---------------------------------------------------------------------------
// Wrapper to provide controlled state in tests
// ---------------------------------------------------------------------------

function ControlledWrapper({
  initial,
  onChangeSpy,
}: {
  initial: HeaderRow[];
  onChangeSpy?: (rows: HeaderRow[]) => void;
}) {
  const [rows, setRows] = useState<HeaderRow[]>(initial);
  function handleChange(next: HeaderRow[]) {
    onChangeSpy?.(next);
    setRows(next);
  }
  return <HeadersEditor rows={rows} onChange={handleChange} valueInputType="text" />;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('HeadersEditor', () => {
  it('renders existing rows', () => {
    render(
      <ControlledWrapper initial={[{ key: 'Authorization', value: 'Bearer abc' }]} />,
    );
    expect((screen.getByTestId('header-key-0') as HTMLInputElement).value).toBe('Authorization');
    expect((screen.getByTestId('header-value-0') as HTMLInputElement).value).toBe('Bearer abc');
  });

  it('Add row — appends a new blank row', () => {
    const onChangeSpy = vi.fn();
    render(
      <ControlledWrapper
        initial={[{ key: 'Authorization', value: 'tok' }]}
        onChangeSpy={onChangeSpy}
      />,
    );

    fireEvent.click(screen.getByTestId('header-add-row'));

    // After state update, second row inputs should exist
    expect(screen.getByTestId('header-key-1')).toBeInTheDocument();
    expect((screen.getByTestId('header-key-1') as HTMLInputElement).value).toBe('');

    // onChange called with 2 rows
    const lastCall = onChangeSpy.mock.calls[onChangeSpy.mock.calls.length - 1][0] as HeaderRow[];
    expect(lastCall).toHaveLength(2);
    expect(lastCall[1]).toEqual({ key: '', value: '' });
  });

  it('Remove row — deletes the correct row by index', () => {
    const onChangeSpy = vi.fn();
    render(
      <ControlledWrapper
        initial={[
          { key: 'Key-A', value: 'val-a' },
          { key: 'Key-B', value: 'val-b' },
        ]}
        onChangeSpy={onChangeSpy}
      />,
    );

    // Remove the first row
    fireEvent.click(screen.getByTestId('header-remove-0'));

    // After removal, only Key-B should remain
    const lastCall = onChangeSpy.mock.calls[onChangeSpy.mock.calls.length - 1][0] as HeaderRow[];
    expect(lastCall).toHaveLength(1);
    expect(lastCall[0].key).toBe('Key-B');
  });

  it('onChange fires with updated array when key input changes', () => {
    const onChangeSpy = vi.fn();
    render(
      <ControlledWrapper
        initial={[{ key: '', value: '' }]}
        onChangeSpy={onChangeSpy}
      />,
    );

    fireEvent.change(screen.getByTestId('header-key-0'), {
      target: { value: 'X-Custom' },
    });

    const lastCall = onChangeSpy.mock.calls[onChangeSpy.mock.calls.length - 1][0] as HeaderRow[];
    expect(lastCall[0].key).toBe('X-Custom');
  });

  it('onChange fires with updated array when value input changes', () => {
    const onChangeSpy = vi.fn();
    render(
      <ControlledWrapper
        initial={[{ key: 'Authorization', value: '' }]}
        onChangeSpy={onChangeSpy}
      />,
    );

    fireEvent.change(screen.getByTestId('header-value-0'), {
      target: { value: 'Bearer new-token' },
    });

    const lastCall = onChangeSpy.mock.calls[onChangeSpy.mock.calls.length - 1][0] as HeaderRow[];
    expect(lastCall[0].value).toBe('Bearer new-token');
  });

  it('renders empty state without add-header helper text', () => {
    render(<ControlledWrapper initial={[]} />);
    // "+ Add header" button still visible even with zero rows
    expect(screen.getByTestId('header-add-row')).toBeInTheDocument();
    // No rows rendered
    expect(screen.queryByTestId('header-key-0')).toBeNull();
  });
});
