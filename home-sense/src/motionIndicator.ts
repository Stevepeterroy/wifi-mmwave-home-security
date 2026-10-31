/** A live signal summary, never a person/occupancy claim. */
export function motionIndicator(
  online: boolean,
  evidence?: {status?: string; csi_motion?: boolean | null; radar_motion?: boolean | null},
  csiConnected = false,
  radarVerified = false,
) {
  if (!online) return {value: 'Unavailable', detail: 'No live sensor transport'};
  if (evidence?.status === 'corroborated_motion')
    return {value: 'Motion signal', detail: 'Current readings indicate movement; not a person count'};
  if (evidence?.status === 'sources_disagree')
    return {value: 'Mixed signals', detail: 'Sensors disagree; check Sensors for details'};
  if (evidence?.radar_motion === true)
    return {value: 'Motion signal', detail: 'Moving reflections detected; not a person count'};
  if (evidence?.csi_motion === true)
    return {value: 'Motion signal', detail: 'Signal changed from the quiet baseline; not a person count'};
  if (evidence?.csi_motion === false && evidence?.radar_motion === false)
    return {value: 'No motion signal', detail: 'No movement indicated now; this does not mean the room is empty'};
  if (evidence?.radar_motion === false)
    return {value: 'No motion signal', detail: 'No moving reflections in the latest reading; other signals not assessed'};
  if (evidence?.csi_motion === false)
    return {value: 'No motion signal', detail: 'No change from the quiet baseline; other signals not assessed'};
  if (csiConnected) return {value: 'Setup needed', detail: 'Calibrate the quiet area on Sensors'};
  if (radarVerified) return {value: 'Start monitoring', detail: 'No fresh radar motion reading yet'};
  return {value: 'Not assessed', detail: 'Waiting for fresh sensing data'};
}
