export type CoverageRecording = {
  participant_id: string;
  module_id: string;
  label: string;
  training_eligible: boolean;
};

/** Collection coverage only: final timing checks and held-out evaluation run offline. */
export function recordingCoverage(recordings: CoverageRecording[]) {
  const eligible = recordings.filter((r) => r.training_eligible);
  const participants = [
    ...new Set(eligible.map((r) => r.participant_id)),
  ].sort();
  const activities = [...new Set(eligible.map((r) => r.label))].sort();
  const modules = [...new Set(eligible.map((r) => r.module_id))].sort();
  const rows = participants.flatMap((participant) =>
    modules.map((module) => {
      const values = eligible.filter(
        (r) => r.participant_id === participant && r.module_id === module,
      );
      return {
        participant,
        module,
        recordings: values.length,
        activities: [...new Set(values.map((r) => r.label))].sort(),
        missingActivities: activities.filter(
          (activity) => !values.some((r) => r.label === activity),
        ),
      };
    }),
  );
  return { eligible: eligible.length, participants, activities, modules, rows };
}
