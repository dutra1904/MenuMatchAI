"use client";

import { useCallback, useEffect, useState } from "react";
import { EMPTY_PROFILE, loadProfile, saveProfile, type Profile } from "@/lib/profile";

export function useProfile() {
  const [profile, setProfileState] = useState<Profile>(EMPTY_PROFILE);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setProfileState(loadProfile());
    setReady(true);
    const sync = () => setProfileState(loadProfile());
    window.addEventListener("mm-profile", sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener("mm-profile", sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  const setProfile = useCallback((value: Profile | ((current: Profile) => Profile)) => {
    setProfileState((current) => {
      const next = typeof value === "function" ? value(current) : value;
      saveProfile(next);
      return next;
    });
  }, []);

  return { profile, setProfile, ready };
}
