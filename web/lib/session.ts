"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { apiFetch } from "@/lib/api-client";

const STORAGE_KEY = "proofline.actorId";
const DEFAULT_ACTOR_ID = "st-01";
const ACTOR_CHANGED_EVENT = "proofline:actor-changed";

export type ActorSummary = {
  id: string;
  name: string;
  role: string;
  clearance: boolean;
};

export function getStoredActorId(): string {
  if (typeof window === "undefined") {
    return DEFAULT_ACTOR_ID;
  }
  return window.localStorage.getItem(STORAGE_KEY) ?? DEFAULT_ACTOR_ID;
}

export function setStoredActorId(actorId: string): void {
  window.localStorage.setItem(STORAGE_KEY, actorId);
  window.dispatchEvent(new CustomEvent(ACTOR_CHANGED_EVENT, { detail: actorId }));
}

function subscribeToActorChange(callback: () => void): () => void {
  window.addEventListener(ACTOR_CHANGED_EVENT, callback);
  return () => window.removeEventListener(ACTOR_CHANGED_EVENT, callback);
}

/** The acting actor id, kept in sync with localStorage across every
 * component that calls this hook (docs/UX.md: "The choice is kept in
 * localStorage"). `useSyncExternalStore` is the correct tool for reading
 * an external store like `localStorage` -- it has no server snapshot to
 * reconcile against (this whole shell is client-rendered) and avoids the
 * "setState during an effect" anti-pattern a plain useEffect would need. */
export function useActorId(): [string, (actorId: string) => void] {
  const actorId = useSyncExternalStore(
    subscribeToActorChange,
    getStoredActorId,
    () => DEFAULT_ACTOR_ID,
  );

  const setActorId = useCallback((next: string) => {
    setStoredActorId(next);
  }, []);

  return [actorId, setActorId];
}

/** Every actor the demo role switcher can become (docs/UX.md Top bar). */
export function useActors(): ActorSummary[] {
  const [actors, setActors] = useState<ActorSummary[]>([]);

  useEffect(() => {
    let cancelled = false;
    apiFetch<{ actors: ActorSummary[] }>("/api/actors")
      .then((body) => {
        if (!cancelled) setActors(body.actors);
      })
      .catch(() => {
        if (!cancelled) setActors([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return actors;
}

export function useCurrentActor(): {
  actorId: string;
  setActorId: (id: string) => void;
  actor: ActorSummary | undefined;
  actors: ActorSummary[];
} {
  const [actorId, setActorId] = useActorId();
  const actors = useActors();
  const actor = actors.find((candidate) => candidate.id === actorId);
  return { actorId, setActorId, actor, actors };
}
