/** A hold reveals details; its release must not also open the 3D room. */
export class RoomGesture {
  private timer: ReturnType<typeof setTimeout> | undefined;
  private held = false;
  private moved = false;
  private startX = 0;
  private startY = 0;
  begin(x: number, y: number, reveal: () => void) {
    this.cancel();
    this.held = false;
    this.moved = false;
    this.startX = x;
    this.startY = y;
    this.timer = setTimeout(() => {
      this.timer = undefined;
      this.held = true;
      reveal();
    }, 450);
  }
  move(x: number, y: number) {
    if (Math.hypot(x - this.startX, y - this.startY) > 10) {
      this.cancel();
      this.moved = true;
    }
  }
  end() {
    if (this.timer) clearTimeout(this.timer);
    this.timer = undefined;
  }
  cancel() {
    this.end();
    this.held = false;
  }
  consumeClick() {
    const suppress = this.held || this.moved;
    this.held = false;
    this.moved = false;
    return suppress;
  }
}
