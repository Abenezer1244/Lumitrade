import Sidebar from "@/components/layout/Sidebar";
import TopBar from "@/components/layout/TopBar";
import { ToastProvider } from "@/components/ui/Toast";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ToastProvider>
      <Sidebar />
      <TopBar />
      <main id="main-content" className="lg:ml-60 pt-20 p-4 lg:p-6 min-h-screen">
        {children}
      </main>
    </ToastProvider>
  );
}
