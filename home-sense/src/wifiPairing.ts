export type PairingDevice = {moduleId?: string; paired: boolean; status: string};
export function pairingTarget(selectedId: string | undefined, selectedConnected: boolean, devices: PairingDevice[]) {
  if (!selectedId) return {ready:false, reason:'Choose a sensor to connect.'};
  if (selectedConnected) return {ready:false, reason:'This sensor is already connected. Choose a different sensor.'};
  if (devices.some(d => d.moduleId === selectedId && d.paired))
    return {ready:false, reason:'This sensor already has an ESP pairing. Choose another sensor or forget the old ESP first.'};
  return {ready:true, reason:'Ready to pair with the selected sensor.'};
}
