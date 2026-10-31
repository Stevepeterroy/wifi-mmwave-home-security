import { useEffect, useState } from "react";
import type { ModelAsset } from "./assets";
import type { ScanFootprint } from "./planProjection";

export function useScanFootprint(model?: ModelAsset) {
  const key = model
    ? JSON.stringify([
        model.id,
        model.scale,
        model.upAxis || "Y",
        model.yaw || 0,
        model.remoteFiles?.map((f) => [f.name, f.sha256]),
      ])
    : "";
  const [state, setState] = useState<{
    key: string;
    footprint?: ScanFootprint;
    error?: string;
  }>();
  useEffect(() => {
    let cancelled = false;
    if (!model) {
      setState(undefined);
      return;
    }
    import("./scanDimensions")
      .then(({ scanDimensions }) => scanDimensions(model))
      .then((footprint) => {
        if (!cancelled) setState({ key, footprint });
      })
      .catch((error) => {
        if (!cancelled) setState({ key, error: (error as Error).message });
      });
    return () => {
      cancelled = true;
    };
  }, [key, model]);
  // Never display the previous scan's dimensions while a new scan is loading.
  return state?.key === key ? state : undefined;
}
