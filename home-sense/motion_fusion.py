"""Conservative corroboration of motion evidence, not a trained fusion model."""
def motion_evidence(csi, node, now):
    state = csi.get('motion', {})
    csi_motion = state.get('status') == 'motion' if csi.get('connected') and state.get('enabled') else None
    frames = [f for f in node.get('frames', []) if 0 <= now-f.get('received_at',0) <= 2]
    radar_motion = None
    if node.get('connected') and node.get('radar_verified') and frames:
        points = [p for f in frames for p in f.get('points', [])]
        if any(abs(p.get('velocity_cm_s',0)) >= 50 for p in points): radar_motion = True
        # An incomplete preview cannot prove no motion was present.
        elif all(not f.get('preview_incomplete',True) for f in frames): radar_motion = False
    if csi_motion is True and radar_motion is True: status = 'corroborated_motion'
    elif csi_motion is None or radar_motion is None: status = 'partial_evidence'
    elif csi_motion != radar_motion: status = 'sources_disagree'
    else: status = 'no_motion_evidence'
    return {'status':status, 'csi_motion':csi_motion, 'radar_motion':radar_motion,
            'method':'two-source motion corroboration', 'trained_fusion':False,
            'accuracy_improvement_verified':False}
