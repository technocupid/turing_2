from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional, Tuple
from datetime import datetime


class InvalidTransition(ValueError):
    pass


class OptimisticLockError(Exception):
    pass


HistoryEntry = Dict[str, Any]
Hook = Callable[[HistoryEntry], None]


class StateMachine:
    """
    Small, generic state machine with:
      - allowed transitions map
      - history recording (with actor / metadata)
      - optimistic versioning (caller may supply expected_version)
      - optional before/after hooks for transitions

    Usage:
      sm = StateMachine(state="placed", allowed_transitions=ALLOWED_TRANSITIONS)
      result = sm.apply("paid", actor=user_id, expected_version=order.version)
      order.status = result["state"]
      order.status_history = result["history"]
      order.version = result["version"]
    """

    def __init__(self, state: str, allowed_transitions: Dict[str, List[str]], version: int = 0,
                 history: Optional[List[HistoryEntry]] = None):
        self.state = state or ""
        self.allowed_transitions = allowed_transitions or {}
        self.version = int(version or 0)
        self.history: List[HistoryEntry] = list(history or [])
        # hooks keyed by (from_state, to_state) tuple
        self._before_hooks: Dict[Tuple[str, str], Hook] = {}
        self._after_hooks: Dict[Tuple[str, str], Hook] = {}

    def can_transition(self, to_state: str) -> bool:
        allowed = self.allowed_transitions.get(self.state, [])
        return to_state in allowed

    def register_before(self, from_state: str, to_state: str, fn: Hook) -> None:
        self._before_hooks[(from_state, to_state)] = fn

    def register_after(self, from_state: str, to_state: str, fn: Hook) -> None:
        self._after_hooks[(from_state, to_state)] = fn

    def _invoke_hook(self, hooks: Dict[Tuple[str, str], Hook], from_state: str, to_state: str, entry: HistoryEntry):
        fn = hooks.get((from_state, to_state))
        if fn:
            try:
                fn(entry)
            except Exception:
                # Hooks must not break state progression; swallow or log in real app.
                pass

    def apply(self, to_state: str, actor: Optional[str] = None, meta: Optional[Dict[str, Any]] = None,
              expected_version: Optional[int] = None) -> Dict[str, Any]:
        """
        Attempt to transition to `to_state`. Raises InvalidTransition or OptimisticLockError.
        Returns dict with keys: state, history (full list), version (new).
        """
        to_state = (to_state or "").strip()
        if not to_state:
            raise InvalidTransition("Empty target state")

        # optimistic lock check
        if expected_version is not None and int(expected_version) != int(self.version):
            raise OptimisticLockError(f"Version mismatch (expected {expected_version}, got {self.version})")

        # idempotent: if already in desired state, no-op (but still return current version)
        if to_state == self.state:
            return {"state": self.state, "history": list(self.history), "version": self.version}

        if not self.can_transition(to_state):
            raise InvalidTransition(f"Invalid transition: {self.state} -> {to_state}")

        # prepare history entry
        entry: HistoryEntry = {
            "from": self.state,
            "to": to_state,
            "at": datetime.utcnow().isoformat(sep=" "),
            "actor": actor,
            "meta": dict(meta or {}),
        }

        # before hook (must not raise)
        self._invoke_hook(self._before_hooks, self.state, to_state, entry)

        # perform transition
        prev_state = self.state
        self.state = to_state
        self.history.append(entry)
        # bump version
        self.version = int(self.version) + 1

        # after hook
        self._invoke_hook(self._after_hooks, prev_state, to_state, entry)

        return {"state": self.state, "history": list(self.history), "version": self.version}