import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

/** Search-box state seeded from, and re-synced to, the `?search=` query param so
 * links (e.g. from the header search) can deep-link into a filtered list. */
export function useUrlSearch() {
  const [searchParams] = useSearchParams();
  const urlSearch = searchParams.get("search");
  const [searchInput, setSearchInput] = useState(urlSearch ?? "");

  useEffect(() => {
    if (urlSearch !== null) setSearchInput(urlSearch);
  }, [urlSearch]);

  return [searchInput, setSearchInput] as const;
}
