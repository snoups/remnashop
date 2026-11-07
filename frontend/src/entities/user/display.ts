import type { TFunction } from "i18next";

import type { UserListItem } from "@entities/user/api";

interface NamedUser {
  name: string;
  telegram_id?: number | null;
  username?: string | null;
  email?: string | null;
  login?: string | null;
  deleted_at?: string | null;
}

// a deleted account keeps neither its name nor a contact; a live one always has one of them
function isDeleted(user: NamedUser): boolean {
  return Boolean(user.deleted_at) || (!user.name && !user.telegram_id && !user.username && !user.email && !user.login);
}

/** The name, "User #id" without one; for rows that carry no contacts to tell a deleted account by. */
export function nameOrUnnamed(name: string, id: number, t: TFunction): string {
  return name || `${t("users.unnamed")} #${id}`;
}

/** One-line label: the name, "User #id" without one, "Deleted user" once deleted. */
export function userLabel(user: NamedUser, id: number, t: TFunction): string {
  if (isDeleted(user)) return t("users.deleted.name");
  return nameOrUnnamed(user.name, id, t);
}

/** The value of a "Name" field: the name, "—" without one, "Deleted user" once deleted. */
export function userNameField(user: NamedUser, t: TFunction): string {
  if (isDeleted(user)) return t("users.deleted.name");
  return user.name || t("common.none");
}

/** A title the caller pairs with the id: the name, "User" without one. */
export function userName(user: UserListItem, t: TFunction): string {
  if (isDeleted(user)) return t("users.deleted.name");
  return user.name || t("users.unnamed");
}

/** "TG: @username · Email: a@b.ru"; the login only when there is no other contact. */
export function userContacts(user: UserListItem, t: TFunction): string {
  return [
    user.telegram_id !== null &&
      t("users.contacts.telegram", { value: user.username ? `@${user.username}` : user.telegram_id }),
    user.email && t("users.contacts.email", { value: user.email }),
    user.telegram_id === null && !user.email && user.login && t("users.contacts.login", { value: user.login }),
  ]
    .filter(Boolean)
    .join(" · ");
}
