interface PillTabsProps<T extends string> {
  items: { key: T; label: string }[];
  activeKey: T | null;
  onSelect: (key: T) => void;
}

/** Tabs share the width when they fit and scroll sideways when they don't --
 * the locale row grows with every language a shop turns on. */
export function PillTabs<T extends string>({ items, activeKey, onSelect }: PillTabsProps<T>) {
  return (
    <div className="no-scrollbar flex gap-1 overflow-x-auto rounded-full border border-white/[0.12] bg-white/[0.03] p-0.5">
      {items.map((item) => (
        <button
          key={item.key}
          type="button"
          onClick={() => onSelect(item.key)}
          className={`flex-1 shrink-0 cursor-pointer whitespace-nowrap rounded-full px-3 py-1.5 text-[12.5px] transition-colors ${
            activeKey === item.key
              ? "bg-accent text-primary"
              : "text-foreground/70 hover:bg-white/[0.06]"
          }`}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
