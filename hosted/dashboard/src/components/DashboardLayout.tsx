import { useSupabaseAuth } from "@/lib/useSupabaseAuth";
import SupabaseLogin from "@/components/SupabaseLogin";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarInset, SidebarMenu, SidebarMenuButton, SidebarMenuItem, SidebarProvider, SidebarTrigger, useSidebar } from "@/components/ui/sidebar";
import { useIsMobile } from "@/hooks/useMobile";
import { Activity, AlertTriangle, BellRing, Bot, ChevronRight, FileText, LayoutDashboard, LogOut, PanelLeft, Settings2 } from "lucide-react";
import { CSSProperties, useEffect, useRef, useState } from "react";
import { useLocation } from "wouter";
import { DashboardLayoutSkeleton } from "./DashboardLayoutSkeleton";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "./ui/dropdown-menu";

const menuItems = [
  { icon: LayoutDashboard, label: "Overview", path: "/" },
  { icon: Activity, label: "Pipeline runs", path: "/runs" },
  { icon: AlertTriangle, label: "Anomaly review", path: "/anomalies" },
  { icon: FileText, label: "Narrative evidence", path: "/narratives" },
  { icon: BellRing, label: "Alert delivery", path: "/alerts" },
  { icon: Settings2, label: "Runtime policy", path: "/settings" },
];

const SIDEBAR_WIDTH_KEY = "veyra-sidebar-width";
const DEFAULT_WIDTH = 272;
const MIN_WIDTH = 220;
const MAX_WIDTH = 380;

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const saved = localStorage.getItem(SIDEBAR_WIDTH_KEY);
    return saved ? parseInt(saved, 10) : DEFAULT_WIDTH;
  });
  const { loading, user } = useSupabaseAuth();
  useEffect(() => { localStorage.setItem(SIDEBAR_WIDTH_KEY, sidebarWidth.toString()); }, [sidebarWidth]);
  if (loading) return <DashboardLayoutSkeleton />;
  if (!user) return <SupabaseLogin />;
  return <SidebarProvider style={{ "--sidebar-width": `${sidebarWidth}px` } as CSSProperties}><DashboardLayoutContent setSidebarWidth={setSidebarWidth}>{children}</DashboardLayoutContent></SidebarProvider>;
}

type Props = { children: React.ReactNode; setSidebarWidth: (width: number) => void };
function DashboardLayoutContent({ children, setSidebarWidth }: Props) {
  const { user, signOut } = useSupabaseAuth();
  const [location, setLocation] = useLocation();
  const { state, toggleSidebar } = useSidebar();
  const [isResizing, setIsResizing] = useState(false);
  const sidebarRef = useRef<HTMLDivElement>(null);
  const isCollapsed = state === "collapsed";
  const isMobile = useIsMobile();
  const activeItem = menuItems.find((item) => item.path === location) ?? menuItems[0];

  useEffect(() => {
    const move = (event: MouseEvent) => { if (!isResizing) return; const left = sidebarRef.current?.getBoundingClientRect().left ?? 0; const width = event.clientX - left; if (width >= MIN_WIDTH && width <= MAX_WIDTH) setSidebarWidth(width); };
    const up = () => setIsResizing(false);
    if (isResizing) { document.addEventListener("mousemove", move); document.addEventListener("mouseup", up); document.body.style.cursor = "col-resize"; document.body.style.userSelect = "none"; }
    return () => { document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up); document.body.style.cursor = ""; document.body.style.userSelect = ""; };
  }, [isResizing, setSidebarWidth]);

  return <>
    <div ref={sidebarRef} className="relative z-50"><Sidebar collapsible="icon" className="border-r border-slate-800/80 bg-[#080d15] text-slate-300" disableTransition={isResizing}>
      <SidebarHeader className="h-20 justify-center border-b border-slate-800/70 px-3"><div className="flex w-full items-center gap-3"><button onClick={toggleSidebar} className="order-2 ml-auto flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-slate-700/70 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400" aria-label="Toggle navigation"><PanelLeft className="h-4 w-4" /></button>{!isCollapsed && <div className="flex min-w-0 items-center gap-3"><div className="veyra-logo-mark"><span /><span /></div><div className="min-w-0"><p className="text-lg font-bold tracking-[0.08em] text-slate-100">VEYRA</p><p className="text-[10px] uppercase tracking-[0.14em] text-slate-500">Market intelligence</p></div></div>}</div></SidebarHeader>
      <SidebarContent className="gap-0 px-2 py-5"><div className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-600 group-data-[collapsible=icon]:hidden">Control plane</div><SidebarMenu>{menuItems.map((item) => { const active = location === item.path; return <SidebarMenuItem key={item.path}><SidebarMenuButton isActive={active} onClick={() => setLocation(item.path)} tooltip={item.label} className="h-11 rounded-xl font-medium text-slate-400 transition-colors hover:bg-slate-800/80 hover:text-slate-100 data-[active=true]:bg-blue-500/10 data-[active=true]:text-blue-300"><item.icon className="h-[18px] w-[18px]" /><span>{item.label}</span>{active && <ChevronRight className="ml-auto h-3.5 w-3.5 group-data-[collapsible=icon]:hidden" />}</SidebarMenuButton></SidebarMenuItem>; })}</SidebarMenu></SidebarContent>
      <SidebarFooter className="border-t border-slate-800/70 p-3"><DropdownMenu><DropdownMenuTrigger asChild><button className="flex w-full items-center gap-3 rounded-xl px-1 py-2 text-left transition-colors hover:bg-slate-800/70 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 group-data-[collapsible=icon]:justify-center"><Avatar className="h-9 w-9 shrink-0 border border-blue-400/30 bg-blue-500/10"><AvatarFallback className="bg-blue-500/10 text-xs font-bold text-blue-300">{(user?.user_metadata?.full_name ?? user?.email ?? "?").charAt(0).toUpperCase()}</AvatarFallback></Avatar><div className="min-w-0 flex-1 group-data-[collapsible=icon]:hidden"><p className="truncate text-sm font-semibold text-slate-200">{user?.user_metadata?.full_name || "Authenticated analyst"}</p><p className="mt-1 truncate text-xs text-emerald-300">● Authenticated</p></div></button></DropdownMenuTrigger><DropdownMenuContent align="end" className="w-48 border-slate-700 bg-slate-900"><DropdownMenuItem onClick={signOut} className="cursor-pointer text-slate-300 focus:bg-slate-800 focus:text-white"><LogOut className="mr-2 h-4 w-4" />Sign out</DropdownMenuItem></DropdownMenuContent></DropdownMenu></SidebarFooter>
    </Sidebar><div className={`absolute right-0 top-0 h-full w-1 cursor-col-resize hover:bg-blue-400/20 ${isCollapsed ? "hidden" : ""}`} onMouseDown={() => setIsResizing(true)} /></div>
    <SidebarInset className="bg-[#070b12]">{isMobile && <div className="sticky top-0 z-40 flex h-14 items-center gap-2 border-b border-slate-800 bg-[#070b12]/95 px-3 backdrop-blur"><SidebarTrigger className="h-9 w-9 rounded-lg border border-slate-700 bg-slate-900 text-slate-300" /><span className="text-sm font-semibold text-slate-200">{activeItem.label}</span></div>}<main className="min-h-screen flex-1">{children}</main></SidebarInset>
  </>;
}
