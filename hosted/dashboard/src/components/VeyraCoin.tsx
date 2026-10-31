import type { CSSProperties } from "react";

type VeyraCoinProps = {
  size?: number;
  className?: string;
};

/**
 * Decorative spinning coin: stands for one market observation.
 * Pure CSS 3D (see .veyra-coin in index.css); respects reduced motion.
 */
export default function VeyraCoin({ size = 44, className = "" }: VeyraCoinProps) {
  return (
    <div className={className} style={{ perspective: 600 }} aria-hidden="true">
      <div className="veyra-coin" style={{ "--s": `${size}px` } as CSSProperties}>
        <i>V</i>
        <i />
        <i />
        <i />
        <i>V</i>
      </div>
    </div>
  );
}
