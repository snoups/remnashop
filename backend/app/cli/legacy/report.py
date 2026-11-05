from dataclasses import dataclass, field


@dataclass(frozen=True, kw_only=True)
class TableCount:
    source: int
    migrated: int

    @property
    def skipped(self) -> int:
        return self.source - self.migrated


@dataclass(frozen=True, kw_only=True)
class SkipEntry:
    table: str
    source_id: str
    reason: str


@dataclass
class MigrationReport:
    counts: dict[str, TableCount] = field(default_factory=dict)
    skips: list[SkipEntry] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def count(self, table: str, source: int, migrated: int) -> None:
        self.counts[table] = TableCount(source=source, migrated=migrated)

    def skip(self, table: str, source_id: str, reason: str) -> None:
        self.skips.append(SkipEntry(table=table, source_id=source_id, reason=reason))

    def render(self) -> str:
        lines = ["Migration report", "", "Tables (source / migrated / skipped):"]
        for table, count in self.counts.items():
            lines.append(f"  {table}: {count.source} / {count.migrated} / {count.skipped}")
        if self.skips:
            lines += ["", "Skipped:"]
            lines += [f"  {s.table} #{s.source_id}: {s.reason}" for s in self.skips]
        if self.notes:
            lines += ["", "Notes:"]
            lines += [f"  {note}" for note in self.notes]
        return "\n".join(lines) + "\n"
