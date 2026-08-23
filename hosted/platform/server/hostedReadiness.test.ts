import { describe, expect, it } from "vitest";
import { buildHostedReadiness } from "./hostedReadiness";

describe("hosted readiness contract", () => {
  it("keeps automatic alert delivery disabled in Module 5A.1", () => {
    const readiness = buildHostedReadiness({
      databaseConfigured: true,
      groqConfigured: true,
      openrouterConfigured: true,
    });

    expect(readiness.pipelineRunLifecycle).toBe("ready");
    expect(readiness.supabasePersistence).toBe("configured");
    expect(readiness.groqNarratives).toBe(true);
    expect(readiness.openrouterFallback).toBe(true);
    expect(readiness.automaticAlertDelivery).toBe("disabled_until_module_5b");
  });

  it("does not expose secret values through readiness", () => {
    const readiness = buildHostedReadiness({
      databaseConfigured: false,
      groqConfigured: true,
      openrouterConfigured: false,
    });

    expect(JSON.stringify(readiness)).not.toMatch(/key|secret|token|password/i);
    expect(readiness.supabasePersistence).toBe("awaiting_server_configuration");
  });
});
