import { NextResponse } from "next/server";
import { backendUrl } from "@/lib/backend-proxy";

// Health check público (6A-B1): solo el estado. No reexpone base, rol, rutas ni versiones del backend.
export async function GET() {
  const headers = { "cache-control": "no-store" };
  try {
    const response = await fetch(`${backendUrl()}/health`, { cache: "no-store" });
    if (!response.ok) {
      return NextResponse.json({ status: "error", service: "deptit-next-frontend" }, { status: 502, headers });
    }
    return NextResponse.json({ status: "ok", service: "deptit-next-frontend" }, { headers });
  } catch {
    return NextResponse.json({ status: "error", service: "deptit-next-frontend" }, { status: 503, headers });
  }
}
