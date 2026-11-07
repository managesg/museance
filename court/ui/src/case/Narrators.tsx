import { DrHoot } from '../cast/DrHoot';
import { McClusky } from '../cast/McClusky';
import type { StageState } from '../engine/types';

/** The medium and the skeptic, small, either side of the line one of them (or the clerk) is saying. */
export function Narrators({ moods, subtitle, stress }: { moods: StageState['moods']; subtitle: StageState['subtitle']; stress: number }) {
  return (
    <div className="narrators">
      <div className="narrators__who" title="McClusky, the medium">
        <McClusky mood={moods.mcclusky} stress={stress} />
      </div>
      <p className="narrators__line" aria-live="polite">
        {subtitle ? (
          <>
            <span className="narrators__speaker">{subtitle.who}</span> {subtitle.text}
          </>
        ) : (
          ' '
        )}
      </p>
      <div className="narrators__who" title="Dr. Hoot, the skeptic">
        <DrHoot mood={moods.hoot} />
      </div>
    </div>
  );
}
