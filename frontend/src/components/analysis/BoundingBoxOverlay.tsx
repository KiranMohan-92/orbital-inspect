import { useEffect, useRef, useCallback } from "react";
import type { DamageItem } from "../../types";

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: "#ff1744",
  SEVERE: "#ff6d00",
  MODERATE: "#ffab00",
  MINOR: "#aeea00",
};

interface BoundingBoxOverlayProps {
  damages: DamageItem[];
  imageRef: React.RefObject<HTMLImageElement | null>;
  visible: boolean;
}

export default function BoundingBoxOverlay({
  damages,
  imageRef,
  visible,
}: BoundingBoxOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const draw = useCallback(() => {
    if (!canvasRef.current || !imageRef.current || !visible) return;

    const img = imageRef.current;
    const canvas = canvasRef.current;

    // Match canvas to image display size
    const rect = img.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;
    canvas.style.width = `${rect.width}px`;
    canvas.style.height = `${rect.height}px`;

    // Position canvas exactly over the image using relative rects
    const parentRect = canvas.parentElement?.getBoundingClientRect();
    if (parentRect) {
      canvas.style.left = `${rect.left - parentRect.left}px`;
      canvas.style.top = `${rect.top - parentRect.top}px`;
    }

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const w = rect.width;
    const h = rect.height;

    damages.forEach((damage, index) => {
      const [yMin, xMin, yMax, xMax] = damage.bounding_box;

      // Convert Gemini 0-1000 coordinates to pixels
      const x = (xMin / 1000) * w;
      const y = (yMin / 1000) * h;
      const bw = ((xMax - xMin) / 1000) * w;
      const bh = ((yMax - yMin) / 1000) * h;

      if (bw <= 0 || bh <= 0) return;

      const color = SEVERITY_COLORS[damage.severity] || SEVERITY_COLORS.MODERATE;
      const isUncertain = damage.uncertain;

      // Semi-transparent fill (8% opacity)
      ctx.fillStyle = color + "14";
      ctx.fillRect(x, y, bw, bh);

      // Border
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      if (isUncertain) {
        ctx.setLineDash([6, 4]);
      } else {
        ctx.setLineDash([]);
      }
      ctx.strokeRect(x, y, bw, bh);
      ctx.setLineDash([]);

      // Label tag above box
      const label = `${isUncertain ? "? " : ""}${damage.label} — ${Math.round(damage.confidence * 100)}%`;
      ctx.font = "bold 11px 'JetBrains Mono', monospace";
      const textMetrics = ctx.measureText(label);
      const tagW = textMetrics.width + 12;
      const tagH = 20;
      const tagX = x;
      const tagY = y > tagH + 4 ? y - tagH - 2 : y + bh + 2;

      // Tag background
      ctx.fillStyle = color;
      if (ctx.roundRect) {
        ctx.beginPath();
        ctx.roundRect(tagX, tagY, tagW, tagH, 3);
        ctx.fill();
      } else {
        ctx.fillRect(tagX, tagY, tagW, tagH);
      }

      // Tag text
      ctx.fillStyle = "#000000";
      ctx.fillText(label, tagX + 6, tagY + 14);
    });
  }, [damages, imageRef, visible]);

  // Redraw on damages change, visibility toggle, or image load/resize
  useEffect(() => {
    // Defer first draw to ensure image has laid out
    const timer = setTimeout(draw, 50);

    const handleResize = () => draw();
    window.addEventListener("resize", handleResize);

    // Observe image element for size changes (handles lazy load)
    const img = imageRef.current;
    let observer: ResizeObserver | null = null;
    if (img) {
      observer = new ResizeObserver(draw);
      observer.observe(img);
      img.addEventListener("load", draw);
    }

    return () => {
      clearTimeout(timer);
      window.removeEventListener("resize", handleResize);
      if (observer) observer.disconnect();
      if (img) img.removeEventListener("load", draw);
    };
  }, [draw, imageRef]);

  if (!visible || damages.length === 0) return null;

  return (
    <canvas
      ref={canvasRef}
      className="absolute pointer-events-none bbox-animate"
      style={{ zIndex: 5 }}
    />
  );
}
