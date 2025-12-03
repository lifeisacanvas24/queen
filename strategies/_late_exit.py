def _apply_late_session_soft_exit(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Universal intraday soft-exit rule.

    Triggers near end-of-day when:
        • playbook ∈ {INTRADAY_TREND, INTRADAY_SCALP}
        • price slipping below VWAP
        • OR price off the intraday high > X%
    """

    tb = (row.get("time_bucket") or "").upper()
    play = (row.get("playbook") or "").upper()
    vwap_zone = (row.get("vwap_zone") or "").upper()

    # Only apply in late session
    if tb not in {"LATE_SESSION", "END_SESSION"}:
        return row

    # Playbooks where we care about fading momentum
    if play not in {"INTRADAY_TREND", "INTRADAY_SCALP"}:
        return row

    # Condition 1: losing VWAP support
    if vwap_zone in {"BELOW", "NEAR_BELOW"}:
        row["action_tag"] = "EXIT"
        row["decision"] = "EXIT"
        row["action_reason"] = "Late-session VWAP fade."
        return row

    # Condition 2: off intraday high by > 0.5%
    try:
        high = float(row.get("day_high") or 0)
        cmp = float(row.get("cmp") or 0)
        if high > 0 and (high - cmp) / high > 0.005:  # >0.5% drop
            row["action_tag"] = "EXIT"
            row["decision"] = "EXIT"
            row["action_reason"] = "Late-session pullback from high."
            return row
    except:
        pass

    return row
