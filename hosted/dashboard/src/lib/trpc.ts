import { createTRPCReact } from "@trpc/react-query";
import type { AppRouter } from "../../../platform/server/routers";

export const trpc = createTRPCReact<AppRouter>();
