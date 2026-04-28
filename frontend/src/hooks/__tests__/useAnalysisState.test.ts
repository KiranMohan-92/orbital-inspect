import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  AGENT_ORDER,
  analysisStateReducer,
  buildInitialAnalysisState,
} from '../useAnalysisState';

const mockRevokeObjectURL = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  global.URL.revokeObjectURL = mockRevokeObjectURL;
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('buildInitialAnalysisState', () => {
  it('has the expected default shape', () => {
    const state = buildInitialAnalysisState();

    expect(state.image).toBeNull();
    expect(state.imagePreviewUrl).toBeNull();
    expect(state.noradId).toBe('');
    expect(state.assetName).toBe('');
    expect(state.externalAssetId).toBe('');
    expect(state.assetType).toBe('satellite');
    expect(state.inspectionEpoch).toBe('');
    expect(state.targetSubsystem).toBe('');
    expect(state.assessmentMode).toBe('PUBLIC_SCREEN');
    expect(state.additionalContext).toBe('');
    expect(state.analysisStatus).toBe('idle');
    expect(state.errorMessage).toBeNull();
    expect(state.analysisId).toBeNull();
    expect(state.showAnnotations).toBe(true);
    expect(state.elapsedTime).toBe(0);
  });

  it('initializes all agents as queued', () => {
    const state = buildInitialAnalysisState();

    for (const name of AGENT_ORDER) {
      expect(state.agents[name].status).toBe('queued');
      expect(state.agents[name].message).toBe('');
      expect(state.agents[name].payload).toBeNull();
      expect(state.agents[name].timestamp).toBeNull();
    }
  });
});

describe('analysisStateReducer', () => {
  it('sets image and preserves context fields', () => {
    const state = {
      ...buildInitialAnalysisState(),
      noradId: '25544',
      assetName: 'ISS Power Channel 2B',
      externalAssetId: 'nasa-iss-2b',
      assetType: 'compute_platform' as const,
      inspectionEpoch: '2026-04-02T12:00Z',
      targetSubsystem: 'solar_array',
      assessmentMode: 'ENHANCED_TECHNICAL' as const,
      additionalContext: 'On-orbit compute bus',
    };
    const file = { name: 'sat.jpg' } as File;

    const next = analysisStateReducer(state, {
      type: 'SET_IMAGE',
      image: file,
      previewUrl: 'blob:mock-url',
    });

    expect(next.image).toBe(file);
    expect(next.imagePreviewUrl).toBe('blob:mock-url');
    expect(next.noradId).toBe('25544');
    expect(next.assetName).toBe('ISS Power Channel 2B');
    expect(next.externalAssetId).toBe('nasa-iss-2b');
    expect(next.assetType).toBe('compute_platform');
    expect(next.inspectionEpoch).toBe('2026-04-02T12:00Z');
    expect(next.targetSubsystem).toBe('solar_array');
    expect(next.assessmentMode).toBe('ENHANCED_TECHNICAL');
    expect(next.additionalContext).toBe('On-orbit compute bus');
  });

  it('revokes the previous preview URL when replacing an image', () => {
    const state = {
      ...buildInitialAnalysisState(),
      imagePreviewUrl: 'blob:old-url',
    };

    analysisStateReducer(state, {
      type: 'SET_IMAGE',
      image: { name: 'next.jpg' } as File,
      previewUrl: 'blob:new-url',
    });

    expect(mockRevokeObjectURL).toHaveBeenCalledWith('blob:old-url');
  });

  it('updates identity fields, evidence context, and analysis id', () => {
    let state = buildInitialAnalysisState();
    state = analysisStateReducer(state, { type: 'SET_NORAD_ID', noradId: '25544' });
    state = analysisStateReducer(state, { type: 'SET_ASSET_NAME', assetName: 'Haven-1 Power Bus Alpha' });
    state = analysisStateReducer(state, { type: 'SET_EXTERNAL_ASSET_ID', externalAssetId: 'vast-h1-bus-a' });
    state = analysisStateReducer(state, { type: 'SET_ASSET_TYPE', assetType: 'solar_array' });
    state = analysisStateReducer(state, {
      type: 'SET_INSPECTION_EPOCH',
      inspectionEpoch: '2026-04-02T12:00Z',
    });
    state = analysisStateReducer(state, {
      type: 'SET_TARGET_SUBSYSTEM',
      targetSubsystem: 'bus',
    });
    state = analysisStateReducer(state, {
      type: 'SET_ASSESSMENT_MODE',
      assessmentMode: 'ENHANCED_TECHNICAL',
    });
    state = analysisStateReducer(state, {
      type: 'SET_ADDITIONAL_CONTEXT',
      additionalContext: 'Deployed array inspection',
    });
    state = analysisStateReducer(state, { type: 'SET_ANALYSIS_ID', analysisId: 'analysis-123' });

    expect(state.noradId).toBe('25544');
    expect(state.assetName).toBe('Haven-1 Power Bus Alpha');
    expect(state.externalAssetId).toBe('vast-h1-bus-a');
    expect(state.assetType).toBe('solar_array');
    expect(state.inspectionEpoch).toBe('2026-04-02T12:00Z');
    expect(state.targetSubsystem).toBe('bus');
    expect(state.assessmentMode).toBe('ENHANCED_TECHNICAL');
    expect(state.additionalContext).toBe('Deployed array inspection');
    expect(state.analysisId).toBe('analysis-123');
  });

  it('starts analysis and clears transient failure state', () => {
    const state = {
      ...buildInitialAnalysisState(),
      analysisStatus: 'failed' as const,
      errorMessage: 'old error',
      analysisId: 'analysis-123',
      elapsedTime: 17,
      agents: {
        ...buildInitialAnalysisState().agents,
        orbital_classification: {
          status: 'complete' as const,
          message: 'done',
          payload: { ok: true },
          timestamp: 123,
        },
      },
    };

    const next = analysisStateReducer(state, { type: 'START_ANALYSIS' });

    expect(next.analysisStatus).toBe('analyzing');
    expect(next.errorMessage).toBeNull();
    expect(next.analysisId).toBeNull();
    expect(next.elapsedTime).toBe(0);
    expect(next.agents.orbital_classification.status).toBe('queued');
  });

  it('updates agent state and preserves existing message or payload when omitted', () => {
    const nowSpy = vi.spyOn(Date, 'now').mockReturnValue(12345);
    const state = buildInitialAnalysisState();

    const first = analysisStateReducer(state, {
      type: 'AGENT_UPDATE',
      agent: 'orbital_classification',
      status: 'thinking',
      message: 'processing',
      payload: { satellite_type: 'communications' },
    });
    const second = analysisStateReducer(first, {
      type: 'AGENT_UPDATE',
      agent: 'orbital_classification',
      status: 'complete',
    });

    expect(first.agents.orbital_classification.status).toBe('thinking');
    expect(first.agents.orbital_classification.message).toBe('processing');
    expect(first.agents.orbital_classification.payload).toEqual({
      satellite_type: 'communications',
    });
    expect(first.agents.orbital_classification.timestamp).toBe(12345);
    expect(second.agents.orbital_classification.status).toBe('complete');
    expect(second.agents.orbital_classification.message).toBe('processing');
    expect(second.agents.orbital_classification.payload).toEqual({
      satellite_type: 'communications',
    });

    nowSpy.mockRestore();
  });

  it('marks completed and completed_partial terminal states', () => {
    let state = buildInitialAnalysisState();

    state = analysisStateReducer(state, { type: 'ANALYSIS_COMPLETE', status: 'completed' });
    expect(state.analysisStatus).toBe('completed');

    state = analysisStateReducer(state, {
      type: 'ANALYSIS_COMPLETE',
      status: 'completed_partial',
    });
    expect(state.analysisStatus).toBe('completed_partial');
  });

  it('marks failed state and stores the error message', () => {
    const next = analysisStateReducer(buildInitialAnalysisState(), {
      type: 'ANALYSIS_ERROR',
      error: 'Connection timeout',
    });

    expect(next.analysisStatus).toBe('failed');
    expect(next.errorMessage).toBe('Connection timeout');
  });

  it('toggles annotations and updates elapsed time', () => {
    let state = buildInitialAnalysisState();

    state = analysisStateReducer(state, { type: 'TOGGLE_ANNOTATIONS' });
    state = analysisStateReducer(state, { type: 'SET_ELAPSED', time: 42 });

    expect(state.showAnnotations).toBe(false);
    expect(state.elapsedTime).toBe(42);
  });

  it('resets to a clean initial state and revokes the preview URL', () => {
    const state = {
      ...buildInitialAnalysisState(),
      image: { name: 'sat.jpg' } as File,
      imagePreviewUrl: 'blob:reset-url',
      noradId: '25544',
      analysisStatus: 'completed_partial' as const,
      errorMessage: 'stale',
    };

    const next = analysisStateReducer(state, { type: 'RESET' });

    expect(mockRevokeObjectURL).toHaveBeenCalledWith('blob:reset-url');
    expect(next).toEqual(buildInitialAnalysisState());
  });
});
