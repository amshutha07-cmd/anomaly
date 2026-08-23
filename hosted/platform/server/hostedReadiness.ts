export type HostedReadiness = {
  pipelineRunLifecycle: "ready" | "pending";
  supabasePersistence: "configured" | "awaiting_server_configuration";
  groqNarratives: boolean;
  openrouterFallback: boolean;
  automaticAlertDelivery: "disabled_until_module_5b";
};

export function buildHostedReadiness(input: {
  databaseConfigured: boolean;
  groqConfigured: boolean;
  openrouterConfigured: boolean;
}): HostedReadiness {
  return {
    pipelineRunLifecycle: "ready",
    supabasePersistence: input.databaseConfigured
      ? "configured"
      : "awaiting_server_configuration",
    groqNarratives: input.groqConfigured,
    openrouterFallback: input.openrouterConfigured,
    automaticAlertDelivery: "disabled_until_module_5b",
  };
}
