import { useLayoutEffect, useState, type ReactNode } from 'react';
import { STAGE_H, STAGE_W } from './layout';
import './stage.css';

const fit = () => Math.min(window.innerWidth / STAGE_W, window.innerHeight / STAGE_H);

/** The fixed 1920x1080 design canvas, scaled by the smaller ratio to fit the window and centred between letterbox bars. */
export function Stage({ children }: { children: ReactNode }) {
  const [scale, setScale] = useState(fit);
  useLayoutEffect(() => {
    // Fullscreen and projector hand-offs both arrive as window resizes.
    const onResize = () => setScale(fit());
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  return (
    <div className="stage-frame">
      <main className="stage" style={{ width: STAGE_W, height: STAGE_H, transform: `translate(-50%, -50%) scale(${scale})` }}>
        {children}
      </main>
    </div>
  );
}
