import { Cpu, Server } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { HostMemory, HostStats, RuntimeProcess } from "@entities/overview/api";
import { formatBytes, formatPercent } from "@shared/lib/format";
import { Section } from "@shared/ui/glass/Section";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { StatusPill } from "@shared/ui/glass/StatusPill";
import { EYEBROW_CLASS, GLASS_INNER_CARD_CLASS, GLASS_PLATE_CLASS } from "@shared/ui/classes";
import { Tag } from "@shared/ui/Tag";
import { RUNTIME_PROCESS_LABELS, formatUptime, usageBarClass } from "@pages/dashboard/runtime";

const SVC_CLASS = `flex flex-col gap-2 p-3.5 ${GLASS_INNER_CARD_CLASS}`;
const KV_CLASS = "flex items-center justify-between gap-2 text-[13px]";

function Kv({ label, value }: { label: string; value: string }) {
  return (
    <div className={KV_CLASS}>
      <span className="text-muted-foreground">{label}</span>
      <b className="font-semibold tabular-nums text-foreground">{value}</b>
    </div>
  );
}

function ProcessCard({ process }: { process: RuntimeProcess }) {
  const { t, i18n } = useTranslation();
  const ms = t("dashboard.runtime.units.millisecond");
  const decimals = new Intl.NumberFormat(i18n.language, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const none = t("common.none");
  const running = process.pid !== null;
  const delay = (value: number | null) => (value === null ? none : `${decimals.format(value)} ${ms}`);
  return (
    <div className={SVC_CLASS}>
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-2.5 text-[13px] font-semibold text-foreground">
          <span className="relative shrink-0">
            <IconCircle icon={Cpu} />
            <i className={`absolute -bottom-px -right-px size-2.5 rounded-full ${running ? "bg-success" : "bg-error"}`} />
          </span>
          <span className="truncate">{RUNTIME_PROCESS_LABELS[process.process] ?? process.process}</span>
        </span>
        {running && <Tag className="font-mono">{t("dashboard.runtime.pid", { pid: process.pid })}</Tag>}
      </div>
      <Kv
        label={t("dashboard.runtime.memory")}
        value={process.rss_bytes === null ? none : formatBytes(process.rss_bytes, i18n.language)}
      />
      <Kv
        label={t("dashboard.runtime.uptime")}
        value={process.uptime_seconds === null ? none : formatUptime(t, process.uptime_seconds)}
      />
      <div className={`${GLASS_PLATE_CLASS} mt-1 flex flex-col gap-1.5 p-2.5`}>
        <span className={EYEBROW_CLASS}>{t("dashboard.runtime.eventLoop")}</span>
        <Kv label={t("dashboard.runtime.eventLoopDelay")} value={delay(process.event_loop_delay_ms)} />
        <Kv label={t("dashboard.runtime.eventLoopP99")} value={delay(process.event_loop_p99_ms)} />
      </div>
    </div>
  );
}

function UsageRow({ label, value, percent }: { label: string; value: string; percent: number }) {
  const width = Math.min(100, Math.max(0, percent));
  return (
    <div className="flex flex-col gap-1.5">
      <Kv label={label} value={value} />
      <div className="h-2 overflow-hidden rounded-full glass-track">
        <div className={`h-full rounded-full ${usageBarClass(percent)}`} style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

function ServerCard({ host, memory }: { host: HostStats | null; memory: HostMemory | null }) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  const disk =
    host && host.disk_total_bytes !== null && host.disk_used_bytes !== null
      ? { total: host.disk_total_bytes, used: host.disk_used_bytes }
      : null;
  const percentOf = (used: number, total: number) => (total > 0 ? (used / total) * 100 : 0);
  const usage = (used: number, total: number) =>
    t("dashboard.runtime.usage", { used: formatBytes(used, language), total: formatBytes(total, language) });
  const decimals = new Intl.NumberFormat(language, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const load =
    host && host.load_1 !== null && host.load_5 !== null && host.load_15 !== null
      ? t("dashboard.runtime.load", {
          l1: decimals.format(host.load_1),
          l5: decimals.format(host.load_5),
          l15: decimals.format(host.load_15),
        })
      : null;
  const sub = [host && t("dashboard.runtime.cores", { count: host.cpu_count }), load].filter(Boolean).join(" · ");

  if (!host && !memory) return null;
  return (
    <div className={SVC_CLASS}>
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <span className="flex items-center gap-2 text-[13px] font-semibold text-foreground">
          <Server className="size-4 text-muted-foreground" />
          {t("dashboard.runtime.server")}
        </span>
        {sub && <span className="text-[12px] text-muted-foreground">{sub}</span>}
      </div>
      <div className="mt-1 grid grid-cols-1 gap-4 sm:grid-cols-[repeat(auto-fit,minmax(200px,1fr))]">
        {host && host.cpu_percent !== null && (
          <UsageRow
            label={t("dashboard.runtime.cpu")}
            value={formatPercent(host.cpu_percent / 100, language)}
            percent={host.cpu_percent}
          />
        )}
        {memory && (
          <UsageRow
            label={t("dashboard.runtime.ram")}
            value={usage(memory.used_bytes, memory.total_bytes)}
            percent={percentOf(memory.used_bytes, memory.total_bytes)}
          />
        )}
        {disk && (
          <UsageRow
            label={t("dashboard.runtime.disk")}
            value={usage(disk.used, disk.total)}
            percent={percentOf(disk.used, disk.total)}
          />
        )}
      </div>
    </div>
  );
}

export function SystemStatusCard({
  runtime,
  memory,
  host,
}: {
  runtime: RuntimeProcess[];
  memory: HostMemory | null;
  host: HostStats | null;
}) {
  const { t, i18n } = useTranslation();
  const running = runtime.filter((process) => process.pid !== null).length;
  const down = runtime.length - running;
  return (
    <Section
      icon={Cpu}
      title={t("dashboard.runtime.title")}
      description={t("dashboard.runtime.description")}
      aside={
        runtime.length > 0 && (
          <>
            {down > 0 && (
              <StatusPill tone="error">{t("dashboard.runtime.down", { n: down.toLocaleString(i18n.language) })}</StatusPill>
            )}
            {running > 0 && (
              <StatusPill tone="success">{t("dashboard.runtime.running", { n: running.toLocaleString(i18n.language) })}</StatusPill>
            )}
          </>
        )
      }
    >
      <div className="flex flex-col gap-3 pt-4">
        {runtime.length > 0 && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {runtime.map((process) => (
              <ProcessCard key={process.process} process={process} />
            ))}
          </div>
        )}
        <ServerCard host={host} memory={memory} />
      </div>
    </Section>
  );
}
