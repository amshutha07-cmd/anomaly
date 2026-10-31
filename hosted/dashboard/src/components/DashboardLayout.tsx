import { useSupabaseAuth } from "@/lib/useSupabaseAuth";
import SupabaseLogin from "@/components/SupabaseLogin";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";
import { useIsMobile } from "@/hooks/useMobile";
import { Activity, AlertTriangle, BellRing, ChevronRight, FileText, LayoutDashboard, LogOut, PanelLeft, Settings2 } from "lucide-react";
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

  useEffect(() => {
    localStorage.setItem(SIDEBAR_WIDTH_KEY, sidebarWidth.toString());
  }, [sidebarWidth]);

  if (loading) return <DashboardLayoutSkeleton />;
  if (!user) return <SupabaseLogin />;

  return (
    <SidebarProvider style={{ "--sidebar-width": `${sidebarWidth}px` } as CSSProperties}>
      <DashboardLayoutContent setSidebarWidth={setSidebarWidth}>{children}</DashboardLayoutContent>
    </SidebarProvider>
  );
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
    const move = (event: MouseEvent) => {
      if (!isResizing) return;
      const left = sidebarRef.current?.getBoundingClientRect().left ?? 0;
      const width = event.clientX - left;
      if (width >= MIN_WIDTH && width <= MAX_WIDTH) setSidebarWidth(width);
    };
    const up = () => setIsResizing(false);
    if (isResizing) {
      document.addEventListener("mousemove", move);
      document.addEventListener("mouseup", up);
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    }
    return () => {
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", up);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [isResizing, setSidebarWidth]);

  const initial = (user?.user_metadata?.full_name ?? user?.email ?? "?").charAt(0).toUpperCase();

  return (
    <>
      <div ref={sidebarRef} className="relative z-50">
        <Sidebar collapsible="icon" className="border-r-2 border-pine bg-mist text-pine" disableTransition={isResizing}>
          <SidebarHeader className="h-20 justify-center border-b-2 border-pine/15 px-3">
            <div className="flex w-full items-center gap-3">
              <button
                onClick={toggleSidebar}
                className="order-2 ml-auto flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border-2 border-pine text-pine transition-colors hover:bg-pine/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-pine"
                aria-label="Toggle navigation"
              >
                <PanelLeft className="h-4 w-4" />
              </button>
              {!isCollapsed && (
                <div className="flex min-w-0 items-center gap-3">
                  <div className="veyra-logo-mark" aria-hidden="true">V</div>
                  <div className="min-w-0">
                    <p className="text-lg font-extrabold tracking-[0.18em] text-pine">VEYRA</p>
                    <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-moss">Evidence-led monitoring</p>
                  </div>
                </div>
              )}
            </div>
          </SidebarHeader>

          <SidebarContent className="gap-0 px-2 py-5">
            <div className="mb-3 px-3 font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-moss group-data-[collapsible=icon]:hidden">
              Control plane
            </div>
            <SidebarMenu>
              {menuItems.map((item) => {
                const active = location === item.path;
                return (
                  <SidebarMenuItem key={item.path}>
                    <SidebarMenuButton
                      isActive={active}
                      onClick={() => setLocation(item.path)}
                      tooltip={item.label}
                      className="h-11 rounded-xl border-2 border-transparent font-bold text-pine transition-colors hover:bg-pine/10 hover:text-pine data-[active=true]:border-pine data-[active=true]:text-pine data-[active=true]:veyra-silver"
                    >
                      <item.icon className="h-[18px] w-[18px]" />
                      <span>{item.label}</span>
                      {active && <ChevronRight className="ml-auto h-3.5 w-3.5 group-data-[collapsible=icon]:hidden" />}
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarContent>

          <SidebarFooter className="border-t-2 border-pine/15 p-3">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="flex w-full items-center gap-3 rounded-xl px-1 py-2 text-left transition-colors hover:bg-pine/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-pine group-data-[collapsible=icon]:justify-center">
                  <Avatar className="h-9 w-9 shrink-0 border-2 border-pine veyra-silver">
                    <AvatarFallback className="bg-transparent text-xs font-extrabold text-pine">{initial}</AvatarFallback>
                  </Avatar>
                  <div className="min-w-0 flex-1 group-data-[collapsible=icon]:hidden">
                    <p className="truncate text-sm font-bold text-pine">{user?.user_metadata?.full_name || "Authenticated analyst"}</p>
                    <p className="mt-1 truncate font-mono text-[10px] uppercase tracking-[0.1em] text-moss">● Session active</p>
                  </div>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48 border-2 border-pine bg-paper">
                <DropdownMenuItem onClick={signOut} className="cursor-pointer font-medium text-pine focus:bg-mist focus:text-pine">
                  <LogOut className="mr-2 h-4 w-4" />
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarFooter>
        </Sidebar>
        <div
          className={`absolute right-0 top-0 h-full w-1 cursor-col-resize hover:bg-pine/20 ${isCollapsed ? "hidden" : ""}`}
          onMouseDown={() => setIsResizing(true)}
        />
      </div>

      <SidebarInset className="bg-sea">
        {isMobile && (
          <div className="sticky top-0 z-40 flex h-14 items-center gap-2 border-b-2 border-pine bg-sea/95 px-3 backdrop-blur">
            <SidebarTrigger className="h-9 w-9 rounded-lg border-2 border-pine bg-paper text-pine" />
            <span className="text-sm font-bold text-pine">{activeItem.label}</span>
          </div>
        )}
        <main className="min-h-screen flex-1">{children}</main>
      </SidebarInset>
    </>
  );
}