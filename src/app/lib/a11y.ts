import type { KeyboardEvent } from "react";

/**
 * Keyboard activation for non-button elements that act as buttons (cards, list
 * rows). Pair with `role="button"` and `tabIndex={0}` so the element is reachable
 * and Enter/Space trigger the same action as a click.
 */
export function onEnterOrSpace<T extends HTMLElement>(
  action: () => void,
): (event: KeyboardEvent<T>) => void {
  return (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      action();
    }
  };
}
