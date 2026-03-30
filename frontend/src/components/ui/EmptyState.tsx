import { PackageOpen, type LucideIcon } from "lucide-react";

interface Props {
  message: string;
  description?: string;
  icon?: LucideIcon;
  action?: { label: string; onClick: () => void };
}

export default function EmptyState({ message, description, icon: Icon = PackageOpen, action }: Props) {
  return (
    <div className="flex flex-col items-center justify-center text-center min-h-[200px] py-12">
      <Icon
        size={40}
        strokeWidth={1.5}
        style={{ color: "var(--color-text-tertiary)" }}
        className="mb-4"
      />
      <p
        className="text-sm font-medium mb-1"
        style={{ color: "var(--color-text-secondary)" }}
      >
        {message}
      </p>
      {description && (
        <p
          className="text-xs max-w-xs"
          style={{ color: "var(--color-text-tertiary)" }}
        >
          {description}
        </p>
      )}
      {action && (
        <button
          onClick={action.onClick}
          className="mt-4 text-sm hover:underline"
          style={{ color: "var(--color-accent)" }}
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
