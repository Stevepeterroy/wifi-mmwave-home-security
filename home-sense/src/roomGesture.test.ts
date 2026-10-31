import { afterEach, it, expect, vi } from "vitest";
import { RoomGesture } from "./roomGesture";
afterEach(() => vi.useRealTimers());
it("reveals on hold and suppresses the resulting click only once", () => {
  vi.useFakeTimers();
  const gesture = new RoomGesture(),
    reveal = vi.fn();
  gesture.begin(0, 0, reveal);
  vi.advanceTimersByTime(450);
  gesture.end();
  expect(reveal).toHaveBeenCalledTimes(1);
  expect(gesture.consumeClick()).toBe(true);
  expect(gesture.consumeClick()).toBe(false);
});
it("allows a quick tap without triggering the hold", () => {
  vi.useFakeTimers();
  const gesture = new RoomGesture(),
    reveal = vi.fn();
  gesture.begin(0, 0, reveal);
  vi.advanceTimersByTime(100);
  gesture.end();
  vi.advanceTimersByTime(500);
  expect(reveal).not.toHaveBeenCalled();
  expect(gesture.consumeClick()).toBe(false);
});
it("cancels a hold during scrolling or pointer cancellation", () => {
  vi.useFakeTimers();
  const gesture = new RoomGesture(),
    reveal = vi.fn();
  gesture.begin(0, 0, reveal);
  gesture.move(0, 30);
  vi.advanceTimersByTime(500);
  expect(reveal).not.toHaveBeenCalled();
  expect(gesture.consumeClick()).toBe(true);
  gesture.begin(0, 0, reveal);
  gesture.cancel();
  vi.advanceTimersByTime(500);
  expect(reveal).not.toHaveBeenCalled();
});
