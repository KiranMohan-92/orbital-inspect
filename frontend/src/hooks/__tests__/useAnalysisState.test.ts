import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAnalysisState } from '../useAnalysisState';

// Mock URL.createObjectURL and URL.revokeObjectURL (not available in jsdom)
const mockCreateObjectURL = vi.fn(() => 'blob:mock-url');
const mockRevokeObjectURL = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  global.URL.createObjectURL = mockCreateObjectURL;
  global.URL.revokeObjectURL = mockRevokeObjectURL;
});

const AGENT_NAMES = [
  'orbital_classification',
  'satellite_vision',
  'orbital_environment',
  'failure_mode',
  'insurance_risk',
] as const;

// ─── Initial state ───────────────────────────────────────────────────────────

describe('initial state', () => {
  it('has correct shape', () => {
    const { result } = renderHook(() => useAnalysisState());
    const { state } = result.current;

    expect(state.image).toBeNull();
    expect(state.imagePreviewUrl).toBeNull();
    expect(state.noradId).toBe('');
    expect(state.analysisStatus).toBe('idle');
    expect(state.errorMessage).toBeNull();
    expect(state.showAnnotations).toBe(true);
    expect(state.elapsedTime).toBe(0);
  });

  it('initialises all agents as queued', () => {
    const { result } = renderHook(() => useAnalysisState());
    const { state } = result.current;

    for (const name of AGENT_NAMES) {
      expect(state.agents[name].status).toBe('queued');
      expect(state.agents[name].message).toBe('');
      expect(state.agents[name].payload).toBeNull();
      expect(state.agents[name].timestamp).toBeNull();
    }
  });
});

// ─── SET_IMAGE ───────────────────────────────────────────────────────────────

describe('SET_IMAGE action', () => {
  it('sets image and creates preview URL', () => {
    const { result } = renderHook(() => useAnalysisState());
    const file = new File(['img'], 'sat.jpg', { type: 'image/jpeg' });

    act(() => {
      result.current.setImage(file);
    });

    expect(result.current.state.image).toBe(file);
    expect(result.current.state.imagePreviewUrl).toBe('blob:mock-url');
    expect(mockCreateObjectURL).toHaveBeenCalledWith(file);
  });

  it('preserves noradId when setting image', () => {
    const { result } = renderHook(() => useAnalysisState());

    act(() => {
      result.current.setNoradId('25544');
    });
    act(() => {
      result.current.setImage(new File(['img'], 'sat.jpg'));
    });

    expect(result.current.state.noradId).toBe('25544');
  });

  it('revokes previous preview URL when a new image is set', () => {
    const { result } = renderHook(() => useAnalysisState());

    act(() => {
      result.current.setImage(new File(['img1'], 'first.jpg'));
    });
    act(() => {
      result.current.setImage(new File(['img2'], 'second.jpg'));
    });

    expect(mockRevokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
  });
});

// ─── SET_NORAD_ID ────────────────────────────────────────────────────────────

describe('SET_NORAD_ID action', () => {
  it('updates noradId', () => {
    const { result } = renderHook(() => useAnalysisState());

    act(() => {
      result.current.setNoradId('25544');
    });

    expect(result.current.state.noradId).toBe('25544');
  });

  it('updates noradId to empty string', () => {
    const { result } = renderHook(() => useAnalysisState());

    act(() => {
      result.current.setNoradId('25544');
    });
    act(() => {
      result.current.setNoradId('');
    });

    expect(result.current.state.noradId).toBe('');
  });
});

// ─── START_ANALYSIS ──────────────────────────────────────────────────────────

describe('START_ANALYSIS action', () => {
  it('sets analysisStatus to analyzing', () => {
    const { result } = renderHook(() => useAnalysisState());

    act(() => {
      result.current.startAnalysis();
    });

    expect(result.current.state.analysisStatus).toBe('analyzing');
  });

  it('resets agents to queued', () => {
    const { result } = renderHook(() => useAnalysisState());

    // First update an agent, then start analysis
    act(() => {
      result.current.updateAgent('orbital_classification', 'complete', 'Done');
    });
    act(() => {
      result.current.startAnalysis();
    });

    expect(result.current.state.agents['orbital_classification'].status).toBe('queued');
  });

  it('clears errorMessage', () => {
    const { result } = renderHook(() => useAnalysisState());

    act(() => {
      result.current.errorAnalysis('previous error');
    });
    act(() => {
      result.current.startAnalysis();
    });

    expect(result.current.state.errorMessage).toBeNull();
  });

  it('resets elapsedTime to 0', () => {
    const { result } = renderHook(() => useAnalysisState());

    act(() => {
      result.current.startAnalysis();
    });

    expect(result.current.state.elapsedTime).toBe(0);
  });
});

// ─── AGENT_UPDATE ────────────────────────────────────────────────────────────

describe('AGENT_UPDATE action', () => {
  it('updates the specified agent status', () => {
    const { result } = renderHook(() => useAnalysisState());

    act(() => {
      result.current.updateAgent('satellite_vision', 'thinking');
    });

    expect(result.current.state.agents['satellite_vision'].status).toBe('thinking');
  });

  it('updates message when provided', () => {
    const { result } = renderHook(() => useAnalysisState());

    act(() => {
      result.current.updateAgent('orbital_classification', 'complete', 'Classification done');
    });

    expect(result.current.state.agents['orbital_classification'].message).toBe('Classification done');
  });

  it('uses ?? to preserve existing message when message is undefined', () => {
    const { result } = renderHook(() => useAnalysisState());

    act(() => {
      result.current.updateAgent('orbital_classification', 'thinking', 'initial message');
    });
    act(() => {
      result.current.updateAgent('orbital_classification', 'complete');
    });

    // message should be preserved (??  operator)
    expect(result.current.state.agents['orbital_classification'].message).toBe('initial message');
  });

  it('updates payload when provided', () => {
    const { result } = renderHook(() => useAnalysisState());
    const payload = { satellite_type: 'communications' };

    act(() => {
      result.current.updateAgent('orbital_classification', 'complete', undefined, payload);
    });

    expect(result.current.state.agents['orbital_classification'].payload).toEqual(payload);
  });

  it('uses ?? to preserve existing payload when payload is undefined', () => {
    const { result } = renderHook(() => useAnalysisState());
    const payload = { satellite_type: 'communications' };

    act(() => {
      result.current.updateAgent('orbital_classification', 'complete', undefined, payload);
    });
    act(() => {
      result.current.updateAgent('orbital_classification', 'error');
    });

    expect(result.current.state.agents['orbital_classification'].payload).toEqual(payload);
  });

  it('sets timestamp on update', () => {
    const { result } = renderHook(() => useAnalysisState());

    act(() => {
      result.current.updateAgent('insurance_risk', 'thinking');
    });

    expect(result.current.state.agents['insurance_risk'].timestamp).not.toBeNull();
  });

  it('does not affect other agents', () => {
    const { result } = renderHook(() => useAnalysisState());

    act(() => {
      result.current.updateAgent('orbital_classification', 'complete');
    });

    expect(result.current.state.agents['satellite_vision'].status).toBe('queued');
    expect(result.current.state.agents['insurance_risk'].status).toBe('queued');
  });
});

// ─── ANALYSIS_COMPLETE ───────────────────────────────────────────────────────

describe('ANALYSIS_COMPLETE action', () => {
  it('sets analysisStatus to complete', () => {
    const { result } = renderHook(() => useAnalysisState());

    act(() => {
      result.current.startAnalysis();
    });
    act(() => {
      result.current.completeAnalysis();
    });

    expect(result.current.state.analysisStatus).toBe('complete');
  });
});

// ─── ANALYSIS_ERROR ──────────────────────────────────────────────────────────

describe('ANALYSIS_ERROR action', () => {
  it('sets analysisStatus to error', () => {
    const { result } = renderHook(() => useAnalysisState());

    act(() => {
      result.current.errorAnalysis('Connection timeout');
    });

    expect(result.current.state.analysisStatus).toBe('error');
  });

  it('stores the error message', () => {
    const { result } = renderHook(() => useAnalysisState());

    act(() => {
      result.current.errorAnalysis('Connection timeout');
    });

    expect(result.current.state.errorMessage).toBe('Connection timeout');
  });
});

// ─── RESET ───────────────────────────────────────────────────────────────────

describe('RESET action', () => {
  it('resets state to initial', () => {
    const { result } = renderHook(() => useAnalysisState());

    act(() => {
      result.current.setNoradId('25544');
      result.current.startAnalysis();
    });
    act(() => {
      result.current.reset();
    });

    expect(result.current.state.analysisStatus).toBe('idle');
    expect(result.current.state.noradId).toBe('');
    expect(result.current.state.image).toBeNull();
  });

  it('revokes preview URL on reset', () => {
    const { result } = renderHook(() => useAnalysisState());

    act(() => {
      result.current.setImage(new File(['img'], 'sat.jpg'));
    });
    act(() => {
      result.current.reset();
    });

    expect(mockRevokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
  });
});
