// Keep the synthetic Windows and browser probes on the same Prepare API contract.
export function p4PreparationRequestUrl(api, projectId, target, expectedVersion) {
  const query = new URLSearchParams({ target, expected_version: String(expectedVersion) });
  return new URL(`${api}/projects/${encodeURIComponent(projectId)}/preparation?${query}`).href;
}
