export type CanvasBounds = {
  left: number;
  top: number;
  width: number;
  height: number;
};

export type CanvasPoint = { x: number; y: number };

export function pointerToCanvasPoint(
  clientX: number,
  clientY: number,
  bounds: CanvasBounds,
  canvasWidth: number,
  canvasHeight: number,
): CanvasPoint {
  if (bounds.width <= 0 || bounds.height <= 0) return { x: 0, y: 0 };
  const x = (clientX - bounds.left) * (canvasWidth / bounds.width);
  const y = (clientY - bounds.top) * (canvasHeight / bounds.height);
  return {
    x: Math.max(0, Math.min(canvasWidth, x)),
    y: Math.max(0, Math.min(canvasHeight, y)),
  };
}

