import os


class Settings:
    PROMETHEUS_URL: str = os.getenv(
        "PROMETHEUS_URL",
        "http://monitoring-kube-prometheus-prometheus.monitoring-ns.svc.cluster.local:9090",
    )
    LOKI_URL: str = os.getenv(
        "LOKI_URL", "http://loki.monitoring-ns.svc.cluster.local:3100"
    )
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash-lite")
    TARGET_NAMESPACES: list[str] = os.getenv(
        "TARGET_NAMESPACES", "donation-ns,ngo-ns,volunteer-ns,monitoring-ns,kubecost"
    ).split(",")
    AUTO_HEALING_ENABLED: bool = os.getenv("AUTO_HEALING_ENABLED", "false").lower() in (
        "true",
        "1",
        "yes",
    )
    ANALYSIS_INTERVAL_SECONDS: int = int(os.getenv("ANALYSIS_INTERVAL_SECONDS", "30"))
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")


settings = Settings()
