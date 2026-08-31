import { Link } from "react-router-dom";

const proofSteps = [
  ["01", "Ingest", "Raw loan tape"],
  ["02", "Inspect", "Exceptions isolated"],
  ["03", "Review", "Human decision"],
  ["04", "Verify", "Hash-linked record"],
];

export default function Home() {
  return (
    <main className="landing-shell">
      <nav className="landing-nav" aria-label="Primary navigation">
        <Link to="/" className="brand-mark" aria-label="LendProof home">
          <span className="brand-glyph">L</span><span>LendProof</span>
        </Link>
        <div className="landing-nav-links"><a href="#workflow">Workflow</a><a href="#principles">Principles</a></div>
        <Link className="landing-try-link" to="/login">Try the demo <span>↗</span></Link>
      </nav>

      <section className="landing-hero">
        <div className="landing-eyebrow"><span />Loan data verification copilot</div>
        <h1>Make every loan record <em>defensible.</em></h1>
        <p className="landing-intro">LendProof turns messy loan files into reviewed, traceable records—without letting an AI make the final call.</p>
        <div className="landing-actions">
          <Link className="landing-primary-cta" to="/login">Try the live workflow <span>→</span></Link>
          <a className="landing-secondary-cta" href="#workflow">See how it works</a>
        </div>
      </section>

      <section className="evidence-panel" id="workflow" aria-label="LendProof workflow">
        <div className="evidence-heading"><p>From source file to trusted data</p><span>Every decision leaves evidence behind.</span></div>
        <div className="evidence-ribbon">
          {proofSteps.map(([number, title, detail], index) => (
            <div className="proof-node" key={title}>
              <span className="proof-index">{number}</span><div className="proof-pulse" aria-hidden="true"><i /></div>
              <strong>{title}</strong><small>{detail}</small>{index < proofSteps.length - 1 && <div className="proof-line" aria-hidden="true" />}
            </div>
          ))}
        </div>
        <div className="evidence-footer"><span className="live-dot" /><span>Built for the Intain Campus FinTech Challenge 2026</span><span className="evidence-hash">SHA-256 VERIFIED LINEAGE</span></div>
      </section>

      <section className="landing-principles" id="principles">
        <p className="section-kicker">Designed for accountable operations</p>
        <div className="principle-grid">
          <article><span>01</span><h2>Find what matters.</h2><p>Configurable checks surface missing, stale, contradictory, and out-of-range loan data before it reaches downstream teams.</p></article>
          <article><span>02</span><h2>Keep humans in control.</h2><p>AI explains a failure and suggests a path forward. A reviewer decides whether to approve, reject, or correct it.</p></article>
          <article><span>03</span><h2>Prove what happened.</h2><p>Uploads, validations, AI output, decisions, and verified records are tied together in an auditable hash chain.</p></article>
        </div>
      </section>

      <footer className="landing-footer"><span>LendProof · Loan Data Verification Copilot</span><Link to="/login">Open demo →</Link></footer>
    </main>
  );
}
