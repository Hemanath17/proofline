import { describe, expect, it, beforeEach } from "vitest";
import { hasSeenTour, markTourSeen, tourRoleFor, tourSteps } from "@/lib/tour";

describe("hasSeenTour / markTourSeen", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("defaults to not seen, and persists after Skip or Finish", () => {
    expect(hasSeenTour()).toBe(false);
    markTourSeen();
    expect(hasSeenTour()).toBe(true);
  });
});

describe("tourRoleFor", () => {
  it("routes preparer to the preparer track and everyone else to the reviewer track", () => {
    expect(tourRoleFor("preparer")).toBe("preparer");
    expect(tourRoleFor("reviewer")).toBe("other");
    expect(tourRoleFor("partner")).toBe("other");
    expect(tourRoleFor(undefined)).toBe("other");
  });
});

describe("tourSteps", () => {
  it("shares the first two steps and branches only the last one", () => {
    const preparer = tourSteps("preparer");
    const other = tourSteps("other");
    expect(preparer).toHaveLength(3);
    expect(other).toHaveLength(3);
    expect(preparer[0]).toEqual(other[0]);
    expect(preparer[1]).toEqual(other[1]);
    expect(preparer[2].key).toBe("proposal");
    expect(other[2].key).toBe("decision");
  });
});
