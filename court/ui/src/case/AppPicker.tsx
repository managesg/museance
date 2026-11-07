import { useEffect, useState } from 'react';
import { fetchApps } from '../feed/apps';
import type { AppEntry } from '../feed/apps';
import './tryit.css';

/** Bring an app: a registered id or name opens its case; anything else says how to register it. */
export function AppPicker(p: { current: string }) {
  const [apps, setApps] = useState<AppEntry[]>([]);
  const [value, setValue] = useState(p.current);
  const [note, setNote] = useState('');

  useEffect(() => {
    void fetchApps().then(setApps);
  }, []);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const v = value.trim();
    if (!v) return;
    const hit = apps.find((a) => a.id === v || a.name.toLowerCase() === v.toLowerCase());
    if (hit) {
      location.search = `?source=runs&app=${encodeURIComponent(hit.id)}`;
      return;
    }
    const id = v.toLowerCase().replace(/[^a-z0-9-]+/g, '-').replace(/^-+|-+$/g, '') || 'my-app';
    setNote(`${v} is not registered yet. To bring it in: add it to fixtures/apps.json with its original URL, then run make case APP=${id} (proposed to the team).`);
  }

  return (
    <form className="apppicker" onSubmit={submit}>
      <label className="tryit-type">
        <span className="tryit-label">App</span>
        <input list="apppicker-apps" value={value} onChange={(e) => { setValue(e.target.value); setNote(''); }} placeholder="app id or name" />
      </label>
      <datalist id="apppicker-apps">
        {apps.map((a) => (
          <option key={a.id} value={a.id}>
            {a.name}{a.fidelity === null ? '' : ` · fidelity ${a.fidelity}`}{a.hasRun ? '' : ' · not run yet'}
          </option>
        ))}
      </datalist>
      <button type="submit">Open</button>
      {note && <p className="apppicker-note" role="status">{note}</p>}
    </form>
  );
}
