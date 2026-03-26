"use client";
import AccountPanel from "@/components/dashboard/AccountPanel";
import TodayPanel from "@/components/dashboard/TodayPanel";
import SystemStatusPanel from "@/components/dashboard/SystemStatusPanel";
import OpenPositionsTable from "@/components/dashboard/OpenPositionsTable";
import MissionControl from "@/components/dashboard/MissionControl";
import { SignalFeed } from "@/components/signals/SignalFeed";
import KillSwitchButton from "@/components/dashboard/KillSwitchButton";

export default function DashboardPage() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <AccountPanel />
        <TodayPanel />
        <SystemStatusPanel />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3"><OpenPositionsTable /></div>
        <div className="lg:col-span-2"><MissionControl /></div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3"><SignalFeed limit={8} compact /></div>
        <div className="lg:col-span-2 flex items-end justify-end">
          <KillSwitchButton />
        </div>
      </div>
    </div>
  );
}
