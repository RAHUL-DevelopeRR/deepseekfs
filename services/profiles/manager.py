"""
Neuron — Profile Manager
==========================
CRUD operations for user profiles.
Each profile is a separate JSON file in storage/profiles/.

Security:
  Scoring weight modification requires username verification
  (gated access — prevents accidental changes).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional, Dict

from app.logger import logger
import app.config as config
from services.profiles.models import Profile, ScoringWeights


_PROFILES_DIR = config.STORAGE_DIR / "profiles"


class ProfileManager:
    """File-based profile CRUD with username-gated weight editing.
    
    Contract:
      - list_profiles() -> List[str]        (profile names)
      - load(name) -> Profile
      - save(profile) -> None
      - delete(name) -> bool
      - get_active() -> Profile
      - set_active(name) -> None
      - modify_weights(name, weights, username) -> (bool, str)
    """

    def __init__(self, profiles_dir: Path = _PROFILES_DIR):
        self._dir = profiles_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._active_file = self._dir / ".active"

        # Ensure default profile exists
        if not (self._dir / "default.json").exists():
            self.save(Profile.default())
            logger.info("ProfileManager: created default profile")

    # ── CRUD ──────────────────────────────────────────────────

    def list_profiles(self) -> List[str]:
        """List all profile names (without .json extension)."""
        return sorted(
            p.stem for p in self._dir.glob("*.json")
            if not p.name.startswith(".")
        )

    def load(self, name: str) -> Optional[Profile]:
        """Load a profile by name."""
        path = self._dir / f"{name}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Profile.from_dict(data)
        except Exception as e:
            logger.warning(f"ProfileManager: failed to load '{name}': {e}")
            return None

    def save(self, profile: Profile):
        """Save a profile to disk."""
        path = self._dir / f"{profile.name}.json"
        try:
            path.write_text(
                json.dumps(profile.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"ProfileManager: failed to save '{profile.name}': {e}")

    def delete(self, name: str) -> bool:
        """Delete a profile. Cannot delete 'default'."""
        if name == "default":
            return False
        path = self._dir / f"{name}.json"
        if path.exists():
            path.unlink()
            logger.info(f"ProfileManager: deleted '{name}'")
            return True
        return False

    def create(self, name: str) -> Profile:
        """Create a new profile from defaults."""
        profile = Profile(name=name)
        self.save(profile)
        return profile

    # ── Active profile ────────────────────────────────────────

    def get_active_name(self) -> str:
        """Get the active profile name."""
        if self._active_file.exists():
            try:
                name = self._active_file.read_text(encoding="utf-8").strip()
                if (self._dir / f"{name}.json").exists():
                    return name
            except Exception:
                pass
        return "default"

    def get_active(self) -> Profile:
        """Load the active profile."""
        name = self.get_active_name()
        profile = self.load(name)
        return profile or Profile.default()

    def set_active(self, name: str) -> bool:
        """Set the active profile."""
        if not (self._dir / f"{name}.json").exists():
            return False
        try:
            self._active_file.write_text(name, encoding="utf-8")
            logger.info(f"ProfileManager: active profile set to '{name}'")
            return True
        except Exception:
            return False

    # ── Gated weight modification ─────────────────────────────

    def modify_weights(
        self,
        name: str,
        weights: ScoringWeights,
        username: str,
    ) -> tuple:
        """Modify scoring weights for a profile.
        
        Requires username verification as a safety gate.
        
        Returns:
            (success: bool, message: str)
        """
        # Verify username matches the OS user
        expected = os.getenv("USERNAME", os.getenv("USER", ""))
        if username.strip().lower() != expected.strip().lower():
            return False, f"Username mismatch. Expected '{expected}'."

        if not weights.validate():
            return False, "Weights must sum to 1.0."

        profile = self.load(name)
        if profile is None:
            return False, f"Profile '{name}' not found."

        profile.scoring = weights
        self.save(profile)
        logger.info(f"ProfileManager: weights updated for '{name}'")
        return True, "Scoring weights updated successfully."

    # ── Export/Import ─────────────────────────────────────────

    def export_profile(self, name: str) -> Optional[str]:
        """Export a profile as JSON string."""
        profile = self.load(name)
        if profile:
            return json.dumps(profile.to_dict(), indent=2)
        return None

    def import_profile(self, json_str: str) -> tuple:
        """Import a profile from JSON string.
        
        Returns (success, name_or_error).
        """
        try:
            data = json.loads(json_str)
            profile = Profile.from_dict(data)
            self.save(profile)
            return True, profile.name
        except Exception as e:
            return False, str(e)
