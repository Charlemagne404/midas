import { cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { EChartsCoreOption } from 'echarts/core';
import { Chart } from './Chart';

const mocks = vi.hoisted(() => ({
  init: vi.fn(),
  setOption: vi.fn(),
  resize: vi.fn(),
  dispose: vi.fn(),
  use: vi.fn(),
}));

vi.mock('echarts/core', () => ({ init: mocks.init, use: mocks.use }));
vi.mock('echarts/charts', () => ({ LineChart: {}, BarChart: {} }));
vi.mock('echarts/components', () => ({
  GridComponent: {},
  TooltipComponent: {},
  LegendComponent: {},
}));
vi.mock('echarts/renderers', () => ({ SVGRenderer: {} }));

class MockResizeObserver implements ResizeObserver {
  readonly observe = vi.fn();
  readonly unobserve = vi.fn();
  readonly disconnect = vi.fn();
}

describe('Chart', () => {
  beforeEach(() => {
    mocks.init.mockReturnValue({
      setOption: mocks.setOption,
      resize: mocks.resize,
      dispose: mocks.dispose,
    });
    Object.defineProperty(globalThis, 'ResizeObserver', {
      configurable: true,
      writable: true,
      value: MockResizeObserver,
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    Reflect.deleteProperty(globalThis, 'ResizeObserver');
  });

  it('updates options on one chart instance and disposes it only when unmounted', () => {
    const firstOption = { series: [{ type: 'line' as const, data: [1, 2] }] };
    const nextOption = { series: [{ type: 'bar' as const, data: [3, 4] }] };
    const { rerender, unmount } = render(
      <Chart label="Market history" option={firstOption as EChartsCoreOption} />,
    );

    expect(mocks.init).toHaveBeenCalledTimes(1);
    expect(mocks.setOption).toHaveBeenCalledTimes(1);
    expect(mocks.setOption).toHaveBeenLastCalledWith(firstOption, { notMerge: true });
    expect(mocks.dispose).not.toHaveBeenCalled();

    rerender(<Chart label="Market history" option={nextOption as EChartsCoreOption} />);

    expect(mocks.init).toHaveBeenCalledTimes(1);
    expect(mocks.setOption).toHaveBeenCalledTimes(2);
    expect(mocks.setOption).toHaveBeenLastCalledWith(nextOption, { notMerge: true });
    expect(mocks.dispose).not.toHaveBeenCalled();

    unmount();

    expect(mocks.dispose).toHaveBeenCalledTimes(1);
  });
});
