"use client";
interface Props { feature: string; phase: number; description: string; unlockCondition: string }
export default function ComingSoon({ feature, phase, description, unlockCondition }: Props) {
  return (
    <div className="flex flex-col items-center justify-center min-h-96 gap-4">
      <div className="glass p-8 max-w-md text-center">
        <span className="text-xs font-label text-warning bg-warning-dim px-2 py-1 rounded mb-4 inline-block">Phase {phase} Feature</span>
        <h2 className="text-heading text-primary mt-3 mb-2">{feature}</h2>
        <p className="text-secondary text-body mb-4">{description}</p>
        <p className="text-tertiary text-sm">Unlocks when: {unlockCondition}</p>
      </div>
    </div>
  );
}
