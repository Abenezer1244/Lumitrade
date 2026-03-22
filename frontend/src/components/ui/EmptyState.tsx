interface Props { message: string; action?: { label: string; onClick: () => void } }
export default function EmptyState({ message, action }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <p className="text-secondary text-sm mb-3">{message}</p>
      {action && <button onClick={action.onClick} className="text-accent text-sm hover:underline">{action.label}</button>}
    </div>
  );
}
