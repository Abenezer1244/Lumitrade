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
      <main id="main-content" className="lg:ml-60 pt-20 px-4 pb-4 lg:px-6 lg:pb-6 min-h-screen">
        {children}
      </main>
    </ToastProvider>
  );
}
