"use client";
import AccountPanel from "@/components/dashboard/AccountPanel";
import TodayPanel from "@/components/dashboard/TodayPanel";
import SystemStatusPanel from "@/components/dashboard/SystemStatusPanel";
import OpenPositionsTable from "@/components/dashboard/OpenPositionsTable";
import { SignalFeed } from "@/components/signals/SignalFeed";
import KillSwitchButton from "@/components/dashboard/KillSwitchButton";

export default function DashboardPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-display text-primary">Dashboard</h1>
      <div className="grid grid-cols-3 gap-4"><AccountPanel /><TodayPanel /><SystemStatusPanel /></div>
      <div className="grid grid-cols-5 gap-4">
        <div className="col-span-3"><OpenPositionsTable /></div>
        <div className="col-span-2"><SignalFeed limit={8} compact /></div>
      </div>
      <div className="flex justify-end"><KillSwitchButton /></div>
    </div>
  );
}
