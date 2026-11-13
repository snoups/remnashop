import type { ClientApps, HourlyOnline, NodesOverview, RecentPayment } from "@entities/overview/api";
import { DebugSection, Specimen } from "@pages/debug/debug-ui";
import { useKit } from "@pages/debug/use-kit";
import { ClientAppsSection } from "@pages/dashboard/ClientAppsCard";
import { FollowHeight, PAIR_ROW_CLASS } from "@pages/dashboard/FollowHeight";
import { NodesCard } from "@pages/dashboard/NodesCard";
import { OnlineCard } from "@pages/dashboard/OnlineCard";
import { RecentPaymentsCard } from "@pages/dashboard/RecentPaymentsCard";

const HOUR_MS = 3_600_000;
const NOW = Date.now();

const HOURLY: HourlyOnline = {
  current: 412,
  points: Array.from({ length: 24 }, (_, index) => ({
    hour: new Date(NOW - (23 - index) * HOUR_MS).toISOString(),
    peak: Math.round(300 + 150 * Math.sin(index / 3)),
  })),
};

const COUNTRIES = ["de", "nl", "fi", "us", "gb", "fr", "pl", "se", "tr", "jp", "sg", "kz", "lv", "ch"];

const NODES: NodesOverview = {
  available: true,
  nodes: COUNTRIES.map((code, index) => ({
    name: `${code.toUpperCase()}-${index + 1}`,
    country_code: code,
    is_connected: index !== 3,
    is_disabled: index === 9,
    users_online: 20 + ((index * 37) % 90),
    traffic_used_bytes: (index + 1) * 7_500_000_000,
    last_status_change: index === 3 ? new Date(NOW - 2 * HOUR_MS).toISOString() : null,
  })),
  countries: COUNTRIES.map((code, index) => ({ country_code: code, nodes: 1, connected: index === 3 ? 0 : 1, users_online: 20 + ((index * 37) % 90) })),
};

const APPS: ClientApps = {
  available: true,
  total_devices: 1840,
  average_per_user: 1.6,
  platforms: ["Android", "iOS", "Windows", "macOS", "Linux", "Android TV"].map((platform, index) => ({
    platform,
    total: 600 - index * 90,
    apps: ["v2rayNG", "Hiddify", "Happ", "Streisand", "FlClash", "Clash Verge"].map((app, appIndex) => ({
      app,
      count: Math.max(5, 200 - index * 25 - appIndex * 30),
    })),
  })),
};

const PAYMENTS: RecentPayment[] = Array.from({ length: 5 }, (_, index) => ({
  transaction_id: index + 1,
  user_id: index + 1,
  name: ["Alice", "Bob", "Carol", "Dave", "Eve"][index],
  plan_name: index % 2 ? "Pro" : "Basic",
  duration_days: 30,
  gateway_type: "TELEGRAM_STARS",
  purchase_type: index % 3 ? "RENEW" : "NEW",
  amount: String(199 + index * 100),
  currency: "RUB",
  paid_at: new Date(NOW - index * HOUR_MS).toISOString(),
}));

export function OverviewSection() {
  const k = useKit();
  return (
    <DebugSection id="overview">
      <Specimen name="FollowHeight · OnlineCard + NodesCard" usage={k("u.followHeightNodes")} wide stage="stretch">
        <div className={PAIR_ROW_CLASS}>
          <OnlineCard hourlyState={{ kind: "ready", data: HOURLY }} refreshKey={0} />
          <FollowHeight>
            <NodesCard state={{ kind: "ready", data: NODES }} />
          </FollowHeight>
        </div>
      </Specimen>
      <Specimen name="FollowHeight · ClientAppsCard + RecentPaymentsCard" usage={k("u.followHeightApps")} wide stage="stretch">
        <div className={PAIR_ROW_CLASS}>
          <FollowHeight>
            <ClientAppsSection state={{ kind: "ready", data: APPS }} />
          </FollowHeight>
          <RecentPaymentsCard payments={PAYMENTS} revenue={{ report_currency: "RUB", today: "1995", yesterday_same_time: "1500", change: 0.33 }} />
        </div>
      </Specimen>
    </DebugSection>
  );
}
