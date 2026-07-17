"use client";

import { useEffect } from "react";
import { requestJson, formatErrorMessage } from "@/lib/http";
import { showToast } from "@/components/toaster";

type UpdateStatus = {
  enabled: boolean;
  available: boolean;
  current_version: string;
  latest_version?: string | null;
  release_url?: string | null;
  notes_url?: string | null;
  error?: string | null;
};

export function UpdateNotice() {
  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const result = await requestJson<UpdateStatus>("/api/update-status");
        if (cancelled || !result.enabled || !result.available || !result.latest_version) return;
        const noticeKey = `datastream-update-notified:${result.latest_version}`;
        if (window.sessionStorage.getItem(noticeKey)) return;
        window.sessionStorage.setItem(noticeKey, "1");
        showToast({
          title: `Ravan ${result.latest_version} is available`,
          description: "Review the release notes and follow the operator-controlled update procedure. No files were changed.",
          variant: "info",
          duration: 12000,
        });
      } catch (error) {
        // Update checks are optional and must never make the application noisy.
        if (process.env.NODE_ENV === "development") console.debug("Update check unavailable", formatErrorMessage(error));
      }
    };
    void check();
    return () => { cancelled = true; };
  }, []);

  return null;
}
