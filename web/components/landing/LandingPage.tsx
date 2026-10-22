import Link from "next/link";
import styles from "./LandingPage.module.css";

const STEPS: Array<{ title: string; body: string }> = [
  {
    title: "Trace it",
    body: "Click any number. See the exact source document, with the field highlighted.",
  },
  {
    title: "Investigate it",
    body: "Checks flag discrepancies as cases. Weigh the evidence, propose a resolution.",
  },
  {
    title: "Sign it off",
    body: "A reviewer or partner approves. The area closes, and the return becomes filing-ready.",
  },
];

const FEATURES: Array<{ title: string; body: string }> = [
  {
    title: "Bidirectional evidence tracing",
    body: "Every number traces back to its source document, and every document shows every number it landed in.",
  },
  {
    title: "Case-based review with role-gated approval",
    body: "Discrepancies become cases. Only the right role can approve, return, or send one to a partner.",
  },
  {
    title: "Versioned decisions and audit history",
    body: "Every revision, decision, and sign-off is recorded. Nothing is overwritten -- undo is a new event.",
  },
  {
    title: "Redaction and role-based access",
    body: "Sensitive values stay masked unless a cleared role reveals them, and every reveal is logged.",
  },
  {
    title: "The AI Evidence Investigator",
    body: "Reads the packet and proposes findings. It can't change a number, close a case, or sign off.",
  },
];

const SHOTS: Array<{ src: string; alt: string; caption: string }> = [
  {
    src: "/landing/queue.png",
    alt: "The review queue, grouped by severity",
    caption: "The queue -- grouped by severity, open on what needs a decision.",
  },
  {
    src: "/landing/case-detail.png",
    alt: "An open case with its evidence and decision bar",
    caption: "A case, open -- the evidence, the proposal, and the decision bar.",
  },
  {
    src: "/landing/trace.png",
    alt: "The trace drawer with a source field highlighted",
    caption: "The trace drawer -- the exact source document, field highlighted.",
  },
];

export function LandingPage() {
  return (
    <div className={styles.page}>
      <header className={styles.topBar}>
        <span className={styles.wordmark}>Proofline</span>
        <Link href="/queue" className={styles.topBarLink}>
          Open the Queue
        </Link>
      </header>

      <section className={`${styles.section} ${styles.hero}`}>
        <h1 className={styles.heroTitle}>Every number, traced to its proof.</h1>
        <p className={styles.heroLede}>
          Proofline is the workpaper behind a household&apos;s 2025 tax return. Every number
          says how we got it, every discrepancy is a case with evidence attached, and every
          sign-off is recorded -- so a reviewer can trust it, and a new hire can follow it.
        </p>
        <div className={styles.ctaRow}>
          <Link href="/queue" className={styles.primaryButton}>
            Launch app
          </Link>
        </div>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>How it works</h2>
        <div className={styles.steps}>
          {STEPS.map((step) => (
            <div key={step.title} className={styles.step}>
              <h3 className={styles.stepTitle}>{step.title}</h3>
              <p className={styles.stepBody}>{step.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>What it does</h2>
        <div className={styles.features}>
          {FEATURES.map((feature) => (
            <div key={feature.title} className={styles.feature}>
              <h3 className={styles.featureTitle}>{feature.title}</h3>
              <p className={styles.featureBody}>{feature.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>See it on a real return</h2>
        <div className={styles.shots}>
          {SHOTS.map((shot) => (
            <figure key={shot.src} className={styles.shot}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img className={styles.shotImage} src={shot.src} alt={shot.alt} loading="lazy" />
              <figcaption className={styles.shotCaption}>{shot.caption}</figcaption>
            </figure>
          ))}
        </div>
      </section>

      <section className={`${styles.section} ${styles.closing}`}>
        <h2 className={styles.closingTitle}>Open the return and follow a number.</h2>
        <div className={styles.ctaRow}>
          <Link href="/queue" className={styles.primaryButton}>
            Launch app
          </Link>
        </div>
      </section>

      <footer className={styles.footer}>
        Proofline -- a CPA workpaper for the Okafor-Lindqvist household, 2025 tax year.
      </footer>
    </div>
  );
}
