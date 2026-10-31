/** Count registered module connections, not USB cables or detected people. */
export function connectionCounts(ids: string[], nodes: Record<string, {connected?: boolean; transport_online?: boolean; radar_verified?: boolean; csi?: {connected?: boolean}}> | undefined) {
  let esps = 0, radars = 0;
  for (const id of new Set(ids)) {
    const node = nodes?.[id];
    const connected = !!(node?.transport_online || node?.connected || node?.csi?.connected);
    if (connected) esps++;
    if (connected && node?.radar_verified) radars++;
  }
  return {esps, radars};
}
