"""Parse the RD60 UART0 point preview; preserve reported vs received counts."""
import re

ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
HEADER = re.compile(r"Point Cloud=(\d+):")
POINT = re.compile(r"P(\d+):\s*x=([+-]?\d+)cm\s+y=([+-]?\d+)cm\s+z=([+-]?\d+)cm\s+([+-]?\d+)cm/s(?:\s+([+-]?\d+))?")


class PreviewParser:
    def __init__(self):
        self.pending = None
        self.sequence = 0

    def flush(self):
        if self.pending is None:
            return []
        frame, self.pending = self.pending, None
        frame["preview_incomplete"] = len(frame["points"]) != frame["reported_points"]
        return [frame]

    def push(self, line, timestamp):
        line = ANSI.sub("", line).replace("[RADAR] ", "")
        match = HEADER.search(line)
        if match:
            completed = self.flush()
            self.sequence += 1
            self.pending = {"sequence": self.sequence, "received_at": timestamp,
                            "reported_points": int(match[1]), "points": []}
            if self.pending["reported_points"] == 0:
                completed += self.flush()
            return completed
        match = POINT.search(line)
        if match and self.pending is not None:
            values = [int(v) if v is not None else None for v in match.groups()]
            if values[0] not in [p["point_index"] for p in self.pending["points"]]:
                self.pending["points"].append(dict(zip(
                    ["point_index", "x_cm", "y_cm", "z_cm", "velocity_cm_s", "unlabelled_value"], values)))
            if len(self.pending["points"]) == self.pending["reported_points"]:
                return self.flush()
        return []


def describe(frame, velocity_threshold=50):
    if frame is None:
        return {"label": "Waiting for a report", "motion": None}
    if frame["reported_points"] == 0:
        return {"label": "No detections in this report", "motion": False}
    if not frame["points"]:
        return {"label": "Reflections reported; coordinates unavailable", "motion": None}
    moving = any(abs(p["velocity_cm_s"]) >= velocity_threshold for p in frame["points"])
    return {"label": "Moving reflections" if moving else "Reflections with low radial speed", "motion": moving}
