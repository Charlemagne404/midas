import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import type { ComponentProps } from 'react';

const LazyChart = lazy(() => import('./Chart').then((module) => ({ default: module.Chart })));
type Props = ComponentProps<typeof LazyChart>;

export function DeferredChart({ label, option }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(() => typeof IntersectionObserver === 'undefined');

  useEffect(() => {
    const node = container.current;
    if (visible || !node) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.target === node && entry.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: '120px' },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [visible]);

  return (
    <div ref={visible ? undefined : container} className="chart-deferred" aria-busy={!visible}>
      {visible ? (
        <Suspense
          fallback={
            <div className="chart chart-placeholder" role="status">
              Loading chart…
            </div>
          }
        >
          <LazyChart option={option} label={label} />
        </Suspense>
      ) : (
        <div className="chart chart-placeholder" role="status">
          Chart loads when visible
        </div>
      )}
    </div>
  );
}
