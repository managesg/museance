// Plain-language meanings shown when a viewer hovers or holds a term.
export const GLOSSARY = {
  original: { title: 'Original', text: 'The dead app as it really ran. SÉANCE keeps it as the reference and never shows its code to the rebuilders.' },
  revival: { title: 'Revival', text: 'The app rebuilt only from the evidence. This is what is on trial.' },
  evidence: { title: 'Evidence', text: 'Everything left behind about the app: pages, screenshots, issues, docs. Tier A is a running copy; tier D is nothing at all.' },
  sheet: { title: 'Behavior sheet', text: 'A plain list of what the app did, written from the evidence. Each line says whether it was seen or guessed.' },
  claim: { title: 'Claim', text: 'A promise about the original app, with a test: do these steps, expect this result.' },
  confidence: { title: 'Confidence', text: 'How sure the medium is that a claim is true, from 0 to 100%. SubQ scores it from the evidence.' },
  bond: { title: 'Bond', text: 'Credits the medium loses if the claim turns out false. It is the price of being wrong.' },
  attack: { title: 'Attack', text: 'A test the skeptic wrote without seeing the claims. It runs on both apps; any difference is a mismatch.' },
  court: { title: 'Court', text: 'Runs every test twice on both apps in a real browser and compares what the screens show. No AI decides the ruling.' },
  mismatch: { title: 'Mismatch', text: 'The revival showed something different from the original for the same steps.' },
  locked: { title: 'Locked', text: 'The claim is true of the original, so it goes into the record.' },
  struck: { title: 'Perjury', text: 'The claim is false: the original did something else. The medium loses the bond.' },
  unsworn: { title: 'Unsworn', text: 'The court could not get a stable answer, so it refuses to rule. It never counts as a strike.' },
  fabricated: { title: 'Fabricated', text: 'The medium admitted it had no evidence for this claim.' },
  fidelity: { title: 'Fidelity', text: 'How often the revival does exactly what the original does, across every test the court ran. 100 means no difference found. It scores the rebuild, not the claims.' },
  credibility: { title: 'Credibility', text: 'The medium’s score. It starts at 1000; a true claim earns a little, a false claim loses its bond.' },
  brier: { title: 'Brier score', text: 'How well the medium’s confidence matched what was true. 0 is perfect; lower is better.' },
  falseStrikes: { title: 'False strikes', text: 'Times the court wrongly struck a behavior we know is correct. It should be 0.' },
  traps: { title: 'Traps caught', text: 'Known tricky inputs where the revival still differs from the original.' },
  repair: { title: 'Repair', text: 'A builder patches the revival using the court’s evidence, then the court tests it again.' },
  tier: { title: 'Evidence tier', text: 'How strong the evidence is: A a running copy, B screenshots or video, C written accounts, D nothing.' },
} as const

export type Term = keyof typeof GLOSSARY
