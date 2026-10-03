import { Database, HardDrive } from "lucide-react";
import type { ComponentType } from "react";

import type { BackupKind } from "@entities/backups/api";

export const BACKUP_KINDS: BackupKind[] = ["DATABASE", "ASSETS"];

export const KIND_ICON: Record<BackupKind, ComponentType<{ className?: string }>> = {
  DATABASE: Database,
  ASSETS: HardDrive,
};
