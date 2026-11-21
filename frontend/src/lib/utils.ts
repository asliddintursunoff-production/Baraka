import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// Teach tailwind-merge our design tokens, otherwise `text-13` (size) and `text-text-4`
// (colour) look like the same group and one of them is dropped.
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [{ text: ["12", "13", "14", "15", "16", "17", "20", "22", "24", "26", "30", "32"] }],
      "text-color": [
        {
          text: [
            "ink", "text-2", "text-3", "text-4", "primary", "primary-hover", "success", "warning",
            "danger", "danger-strong", "warning-accent", "surface",
          ],
        },
      ],
      rounded: [{ rounded: ["card", "inner", "btn", "btn-lg", "pill"] }],
    },
  },
});

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
