interface Props { children: React.ReactNode; title: string }
export default function PageContainer({ children, title }: Props) {
  return (
    <div className="ml-60 p-6 min-h-screen">
      <h1 className="text-display text-primary mb-6">{title}</h1>
      {children}
    </div>
  );
}
