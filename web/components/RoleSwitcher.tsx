"use client";

import { useCurrentActor } from "@/lib/session";
import styles from "./RoleSwitcher.module.css";

/** docs/UX.md Top bar: "the role switcher... shows the acting person's
 * name, role and clearance, and is labelled 'Demo role switcher', setting
 * X-Proofline-Actor." Not authentication -- see
 * proofline/security/dependencies.py on the API side. */
export function RoleSwitcher() {
  const { actorId, setActorId, actors } = useCurrentActor();

  return (
    <label className={styles.wrap}>
      <span className={styles.caption}>Demo role switcher</span>
      <select
        className={styles.select}
        value={actorId}
        onChange={(event) => setActorId(event.target.value)}
        aria-label="Demo role switcher: acting as"
      >
        {actors.map((actor) => (
          <option key={actor.id} value={actor.id}>
            {actor.name} · {actor.role}
            {actor.clearance ? "" : " (no clearance)"}
          </option>
        ))}
      </select>
    </label>
  );
}
