"use client";

import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, Search } from "lucide-react";
import { Input } from "@/components/ui/input";

export type SearchableSelectOption = {
  value: string;
  label: string;
  searchText?: string;
};

export function SearchableSelect({
  value,
  options,
  onChange,
  placeholder = "Select an option",
  searchPlaceholder = "Search options...",
  disabled = false,
  className = "",
}: {
  value: string;
  options: SearchableSelectOption[];
  onChange: (value: string) => void;
  placeholder?: string;
  searchPlaceholder?: string;
  disabled?: boolean;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);
  const selected = options.find((option) => option.value === value);
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const filtered = normalizedQuery
    ? options.filter((option) => `${option.label} ${option.searchText ?? option.value}`.toLocaleLowerCase().includes(normalizedQuery))
    : options;

  useEffect(() => {
    if (!open) return;
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", closeOnOutsideClick);
    return () => document.removeEventListener("mousedown", closeOnOutsideClick);
  }, [open]);

  const select = (next: string) => {
    onChange(next);
    setQuery("");
    setOpen(false);
  };

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <button
        type="button"
        className="app-select flex w-full items-center justify-between text-left disabled:cursor-not-allowed disabled:opacity-60"
        aria-haspopup="listbox"
        aria-expanded={open}
        disabled={disabled}
        onClick={() => setOpen((current) => !current)}
      >
        <span className={selected ? "truncate text-text-primary" : "truncate text-text-secondary"}>{selected?.label ?? placeholder}</span>
        <ChevronDown className={`ml-2 size-4 shrink-0 text-text-secondary transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open ? (
        <div className="absolute z-50 mt-1 w-full min-w-[16rem] overflow-hidden rounded-lg border border-border-subtle bg-surface-raised p-2 shadow-xl">
          <div className="relative mb-2">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-text-secondary" />
            <Input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={searchPlaceholder}
              aria-label={searchPlaceholder}
              className="h-8 pl-8 text-xs"
            />
          </div>
          <div className="max-h-56 overflow-y-auto" role="listbox" aria-label={placeholder}>
            <button type="button" role="option" aria-selected={!value} onClick={() => select("")} className="flex w-full items-center rounded-md px-2 py-2 text-left text-xs text-text-secondary hover:bg-surface-2">
              {placeholder}
            </button>
            {filtered.map((option) => (
              <button key={option.value} type="button" role="option" aria-selected={option.value === value} onClick={() => select(option.value)} className="flex w-full items-start gap-2 rounded-md px-2 py-2 text-left text-xs text-text-primary hover:bg-accent-subtle">
                <Check className={`mt-0.5 size-3.5 shrink-0 ${option.value === value ? "text-accent" : "text-transparent"}`} />
                <span className="break-words">{option.label}</span>
              </button>
            ))}
            {!filtered.length ? <p className="px-2 py-3 text-xs text-text-secondary">No matching options.</p> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
