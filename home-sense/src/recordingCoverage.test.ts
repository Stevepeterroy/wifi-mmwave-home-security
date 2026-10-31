import { expect, it } from "vitest";
import { recordingCoverage } from "./recordingCoverage";

it("counts only eligible reviews and exposes gaps across radar pairs", () => {
  const coverage = recordingCoverage([
    {
      participant_id: "p1",
      module_id: "radar1",
      label: "walking",
      training_eligible: true,
    },
    {
      participant_id: "p1",
      module_id: "radar1",
      label: "walking",
      training_eligible: true,
    },
    {
      participant_id: "p2",
      module_id: "radar2",
      label: "sitting",
      training_eligible: true,
    },
    {
      participant_id: "p3",
      module_id: "radar3",
      label: "standing",
      training_eligible: false,
    },
  ]);
  expect(coverage.eligible).toBe(3);
  expect(coverage.participants).toEqual(["p1", "p2"]);
  expect(coverage.modules).toEqual(["radar1", "radar2"]);
  expect(coverage.activities).toEqual(["sitting", "walking"]);
  expect(
    coverage.rows.find((r) => r.participant === "p1" && r.module === "radar1"),
  ).toMatchObject({ recordings: 2, missingActivities: ["sitting"] });
  expect(
    coverage.rows.find((r) => r.participant === "p1" && r.module === "radar2"),
  ).toMatchObject({ recordings: 0, missingActivities: ["sitting", "walking"] });
});
it("does not invent collection coverage for an empty library", () => {
  expect(recordingCoverage([])).toEqual({
    eligible: 0,
    participants: [],
    activities: [],
    modules: [],
    rows: [],
  });
});
