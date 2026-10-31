import VeyraCoin from "./VeyraCoin";

type VeyraRadarProps = {
  size?: number;
  /** Show the coin orbiting the outer ring. */
  orbit?: boolean;
  /** Show the orange anomaly blip (orange is reserved for anomalies). */
  anomaly?: boolean;
  className?: string;
};

/**
 * Decorative radar. Rings = monitoring cycles, sweep = the scheduled scan,
 * orange blip = a flagged anomaly. Purely visual; no data is shown here.
 */
export default function VeyraRadar({ size = 300, orbit = true, anomaly = true, className = "" }: VeyraRadarProps) {
  const ringRadius = (140 * size) / 300;
  const coinSize = Math.max(28, Math.round(size / 8));

  return (
    <div className={`relative ${className}`} style={{ width: size, height: size }} aria-hidden="true">
      <svg viewBox="0 0 300 300" width={size} height={size}>
        <circle cx="150" cy="150" r="140" className="fill-paper" />
        {[135, 100, 65, 30].map((r) => (
          <circle key={r} cx="150" cy="150" r={r} fill="none" className="stroke-pine/30" strokeWidth="2" />
        ))}
        <path className="veyra-sweep fill-pine/20" d="M150 150 L150 10 A140 140 0 0 1 249 51 Z" />
        <circle cx="100" cy="90" r="5" className="fill-pine" />
        <circle cx="215" cy="190" r="5" className="fill-pine" />
        {anomaly && (
          <>
            <circle className="veyra-ping stroke-signal" cx="200" cy="100" r="7" fill="none" strokeWidth="3" />
            <circle cx="200" cy="100" r="7" className="fill-signal stroke-pine" strokeWidth="2" />
          </>
        )}
      </svg>
      {orbit && (
        <div className="veyra-orbit-spin absolute left-0 top-0" style={{ width: size, height: size }}>
          <div className="absolute" style={{ left: size / 2 - coinSize / 2, top: size / 2 - ringRadius - coinSize / 2 }}>
            <VeyraCoin size={coinSize} />
          </div>
        </div>
      )}
    </div>
  );
}
