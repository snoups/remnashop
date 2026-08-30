import { apiGet } from "./http";

export interface SystemMetadata {
  version: string;
  repository_url: string;
  git: {
    commit_sha: string | null;
    commit_date: string | null;
    branch: string | null;
    is_official_build: boolean;
  };
}

export function getSystemMetadata(): Promise<SystemMetadata> {
  return apiGet<SystemMetadata>("/system/metadata");
}
