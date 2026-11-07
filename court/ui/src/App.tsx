import { CourtroomBackdrop } from './set/Courtroom'

// Placeholder until the stage integration replaces it; the set's SVG letterboxes itself at 16:9.
export default function App() {
  return (
    <main style={{ height: '100%' }}>
      <CourtroomBackdrop />
    </main>
  )
}
