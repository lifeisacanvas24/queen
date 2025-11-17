#queen/settings/meta_controller_cfg.py
META_CTRL = {
    "model_file": "tactical_ai_model.pkl",
    "retrain_interval_hours": 24,
    "drift_threshold": 0.10,
    "last_retrain_ts": None,
    # "event_log": "tactical_event_log.csv"  # only if you still keep a CSV log
}
