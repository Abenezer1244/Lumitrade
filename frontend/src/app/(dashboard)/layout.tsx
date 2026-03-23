import Sidebar from "@/components/layout/Sidebar";
import TopBar from "@/components/layout/TopBar";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <Sidebar />
      <TopBar />
      <main className="lg:ml-60 pt-14 p-4 lg:p-6 min-h-screen">{children}</main>
    </>
  );
}
